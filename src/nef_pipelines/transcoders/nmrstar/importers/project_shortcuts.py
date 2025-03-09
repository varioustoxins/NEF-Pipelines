BMRB_AUTO_MIRROR = "**auto**"
BMRB_URL_TEMPLATE = "https://bmrb.io/ftp/pub/bmrb/entry_directories/bmr{entry_number}/bmr{entry_number}_3.str"
BMRB_JAPAN_URL_TEMPLATE =  "https://bmrb.pdbj.org/ftp/pub/bmrb/entry_lists/nmr-star3.1/bmr{entry_number}.str"
BMRB_ITALY_URL_TEMPLATE = "https://bmrb.cerm.unifi.it/ftp/pub/bmrb/entry_directories/bmr{entry_number}/bmr{entry_number}_3.str"

# TODO these should be in a resource file?
SHORTCUTS = {
    "UBIQUITIN": "bmr5387",
    "GB1": "bmr7280",
    "GB3": "bmr25910",
    "MBP": "bmr4354",
    "MSG": "bmr5471",
    "INSULIN": "bmr1000",
}

SHORTCUT_ENTRYS = {name: id[3:] for name, id in SHORTCUTS.items()}
SHORTCUT_URLS = {
    name: BMRB_URL_TEMPLATE.format(entry_number=entry_number)
    for name, entry_number in SHORTCUT_ENTRYS.items()
}
SHORTCUT_NAMES = ", ".join({name.lower(): name for name in SHORTCUTS.keys()})
