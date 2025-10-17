# -*- coding: utf-8 -*-
# run_pipeline.py (v5)
# - Lọc bỏ các key có < 50 người
# - Thêm cột 'universities_category' từ edges_category vào final_long/final_wide
# - Xuất CSV utf-8-sig và Excel .xlsx (font tiếng Việt chuẩn)

import os, re, time
import requests
import pandas as pd
import mwparserfromhell as mw
from unidecode import unidecode
from urllib.parse import quote

API = "https://vi.wikipedia.org/w/api.php"
S = requests.Session()
S.headers.update({
    "User-Agent": "wiki-alumni-us-vi/1.0 (+github.com/MeragGOD)",
    "Accept": "application/json",
})

ROOT_CAT = "Thể loại:Cựu sinh viên trường đại học và cao đẳng ở Hoa Kỳ"
OUT_DIR = "data"
KEY_MIN_PEOPLE = 50  # <—— chỉ giữ key có ít nhất 50 người

os.makedirs(OUT_DIR, exist_ok=True)

def wiki_url_from_title(title: str) -> str:
    return "https://vi.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))

def _get_json(params, retries=5, backoff=0.8):
    base = {"format": "json", "utf8": 1, "origin": "*"}
    q = {**params, **base}
    for i in range(retries):
        r = S.get(API, params=q, timeout=30)
        if r.ok:
            try:
                return r.json()
            except requests.exceptions.JSONDecodeError:
                sample = r.text[:200]
                raise RuntimeError(f"API không trả JSON. Ví dụ nội dung: {sample!r}")
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(backoff*(i+1)); continue
        r.raise_for_status()

def category_members(cmtitle, cmtype="page", limit=500):
    params = {
        "action":"query","list":"categorymembers","cmtitle":cmtitle,
        "cmtype":cmtype,"cmlimit":str(limit),
    }
    cont=None
    while True:
        if cont: params.update(cont)
        data=_get_json(params)
        for it in data["query"]["categorymembers"]:
            yield it
        cont=data.get("continue")
        if not cont: break
        time.sleep(0.05)

def get_wikitext(title):
    data=_get_json({"action":"parse","page":title,"prop":"wikitext"})
    return data["parse"]["wikitext"]["*"]

# —— Chuẩn hoá key
KEY_MAP = {
    "alma mater":"alma_mater","alma_mater":"alma_mater",
    "học_vấn":"alma_mater","hoc van":"alma_mater","giáo dục":"alma_mater","giao duc":"alma_mater",
    "học vị":"degree","hoc vi":"degree",
    "ngành":"major","nganh":"major",
    "field":"field","ngành nghiên cứu":"field","nganh nghien cuu":"field",
    "quốc tịch":"nationality","quoc tich":"nationality",
    "nghề nghiệp":"occupation","nghe nghiep":"occupation",
    "giải thưởng":"awards","giai thuong":"awards",
    "trường":"institution","truong":"institution",
    "known for":"known_for","nổi tiếng vì":"known_for","noi tieng vi":"known_for",
}
def norm_key(k: str) -> str:
    k = unidecode(k.strip().lower())
    k = re.sub(r"\s+", " ", k)
    return KEY_MAP.get(k, k)

# —— Làm sạch value
def clean_wikilinks(s: str) -> str:
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    s = re.sub(r"<br\s*/?>", ";", s, flags=re.I)
    s = re.sub(r"\{\{.*?\}\}", " ", s)
    s = re.sub(r"\s*;\s*", ";", s)
    s = s.replace("\u00a0", " ")
    return s.strip(" .\n\t-–—")

def split_values(v: str):
    v = clean_wikilinks(v)
    parts = re.split(r";|\n|•|, và | và |,|\u2022", v)
    parts = [p.strip(" .\t-–—") for p in parts if p and len(p.strip()) >= 2]
    return parts or []

def main():
    print("[1/6] Lấy sub-categories (các trường)...")
    subcats = list(category_members(ROOT_CAT, "subcat"))
    print(f"  -> {len(subcats)} sub-categories")

    print("[2/6] Lấy tất cả trang nhân vật + edges (category)...")
    people = set()
    edges = []
    for sc in subcats:
        uni_name = sc["title"].replace("Thể loại:Cựu sinh viên ", "").strip()
        for page in category_members(sc["title"], "page"):
            person = page["title"]
            people.add(person)
            edges.append({
                "person": person,
                "person_url": wiki_url_from_title(person),
                "university": uni_name,
                "university_url": wiki_url_from_title(uni_name),
                "source": "category",
            })
    print(f"  -> {len(people)} người; {len(edges)} cạnh từ category")

    edges_df = pd.DataFrame(edges)
    # gộp các trường theo người -> 'universities_category'
    uni_by_person = (
        edges_df
        .drop_duplicates(["person","university"])
        .groupby(["person","person_url"])["university"]
        .apply(lambda s: "; ".join(sorted(set(s))))
        .reset_index()
        .rename(columns={"university":"universities_category"})
    )

    # Lưu people & edges (utf-8-sig)
    people_rows = [{"person_title": t, "person_url": wiki_url_from_title(t)} for t in sorted(people)]
    pd.DataFrame(people_rows).to_csv(os.path.join(OUT_DIR, "people_all.csv"),
                                     index=False, encoding="utf-8-sig")
    edges_df.to_csv(os.path.join(OUT_DIR, "edges_category.csv"),
                    index=False, encoding="utf-8-sig")

    print("[3/6] Đọc Infobox của từng nhân vật...")
    rows = []
    people_list = sorted(people)
    for i, person in enumerate(people_list, 1):
        try:
            wikitext = get_wikitext(person)
            code = mw.parse(wikitext)
            for tpl in code.filter_templates():
                if "infobox" in tpl.name.strip().lower():
                    for p in tpl.params:
                        k = norm_key(str(p.name))
                        v = str(p.value).strip()
                        if not v:
                            continue
                        for item in split_values(v):
                            rows.append({
                                "person": person,
                                "person_url": wiki_url_from_title(person),
                                "key": k,
                                "value": item
                            })
                    break
        except Exception:
            pass
        if i % 100 == 0:
            print(f"  parsed {i}/{len(people_list)}")
        time.sleep(0.05)

    long_df = pd.DataFrame(rows)
    long_df.to_csv(os.path.join(OUT_DIR, "infobox_long.csv"),
                   index=False, encoding="utf-8-sig")
    print(f"  -> infobox_long rows: {len(long_df)}")

    print("[4/6] Thống kê theo key & lọc key >= {KEY_MIN_PEOPLE} người ...")
    key_freq = (
        long_df.groupby("key")["person"]
        .nunique()
        .reset_index(name="n_people")
        .sort_values("n_people", ascending=False)
    )
    key_freq.to_csv(os.path.join(OUT_DIR, "key_frequent.csv"),
                    index=False, encoding="utf-8-sig")

    keys_keep = set(key_freq.loc[key_freq["n_people"] >= KEY_MIN_PEOPLE, "key"])
    filtered_long = long_df[long_df["key"].isin(keys_keep)].copy()

    print(f"  -> Giữ {len(keys_keep)} key; bỏ {len(key_freq)-len(keys_keep)} key hiếm")

    print("[5/6] Xuất FINAL-LONG (merge 'universities_category') ...")
    final_long = (
        filtered_long
        .merge(uni_by_person, on=["person","person_url"], how="left")
        [["person","person_url","universities_category","key","value"]]
        .sort_values(["person","key","value"])
    )
    final_long.to_csv(os.path.join(OUT_DIR, "final_long.csv"),
                      index=False, encoding="utf-8-sig")

    print("[6/6] Tạo FINAL-WIDE (mỗi key = 1 cột, gộp nhiều value bằng '; ') ...")
    if not filtered_long.empty:
        # gộp (person, key) -> join unique values '; '
        agg = (
            filtered_long
            .drop_duplicates(["person","key","value"])
            .groupby(["person","person_url","key"])["value"]
            .apply(lambda s: "; ".join(sorted(set(s))))
            .reset_index()
        )
        wide = agg.pivot(index=["person","person_url"], columns="key", values="value").reset_index()
        # nhập thêm cột universities_category
        wide = wide.merge(uni_by_person, on=["person","person_url"], how="left")
        # sắp cột
        front = ["person","person_url","universities_category"]
        rest = sorted([c for c in wide.columns if c not in front])
        wide = wide[front + rest]

        wide.to_csv(os.path.join(OUT_DIR, "final_wide.csv"),
                    index=False, encoding="utf-8-sig")

        # Excel .xlsx (không lỗi font)
        xlsx_path = os.path.join(OUT_DIR, "final_wide.xlsx")
        with pd.ExcelWriter(xlsx_path, engine="xlsxwriter") as writer:
            wide.to_excel(writer, sheet_name="final_wide", index=False)
        print("  -> Đã tạo:", xlsx_path)
    else:
        print("  (Không có dữ liệu sau khi lọc key)")

    print("Hoàn tất.")
    print(f"  People             : {len(people)}")
    print(f"  Infobox rows       : {len(long_df)}")
    print(f"  Keys (tổng)        : {len(key_freq)}")
    print(f"  Keys giữ (>= {KEY_MIN_PEOPLE}) : {len(keys_keep)}")
    print(f"  -> File nằm trong thư mục: {OUT_DIR}/")

if __name__ == "__main__":
    main()
