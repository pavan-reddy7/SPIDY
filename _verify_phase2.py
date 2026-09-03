"""
Automated verification of the SPIDY Phase 2 manual test plan.
Runs without launching real applications (tests logic only).
Prints PASS/FAIL for every test case.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from main import create_registry
from intent_parser import parse_intent

r = create_registry()

pass_count = 0
fail_count = 0


def check(label: str, text: str, expected_tool: str | None,
          expected_target: str | None = None,
          expect_blocked: bool = False):
    global pass_count, fail_count
    match = parse_intent(text, r)

    if expected_tool is None:
        # Should NOT match anything
        ok = match is None
        if ok:
            print(f"  PASS [{label}] '{text}' -> (no match, correct)")
            pass_count += 1
        else:
            tool, params = match
            print(f"  FAIL [{label}] '{text}' -> matched {tool.name} (should be None)")
            fail_count += 1
        return

    if match is None:
        print(f"  FAIL [{label}] '{text}' -> no match (expected {expected_tool})")
        fail_count += 1
        return

    tool, params = match
    target = params.get("target", "")
    keyword = params.get("_keyword", "")

    tool_ok = tool.name == expected_tool
    target_ok = True
    if expected_target is not None:
        target_ok = expected_target.lower() in (target + keyword).lower()

    if tool_ok and target_ok:
        print(f"  PASS [{label}] '{text}' -> {tool.name} kw={keyword!r} target={target!r}")
        pass_count += 1
    else:
        reasons = []
        if not tool_ok:
            reasons.append(f"tool={tool.name} expected={expected_tool}")
        if not target_ok:
            reasons.append(f"target={target!r} kw={keyword!r} expected to contain {expected_target!r}")
        print(f"  FAIL [{label}] '{text}' -> {', '.join(reasons)}")
        fail_count += 1


# ------------------------------------------------------------------ #
print("\n=== 1. APPLICATION LAUNCHING (tests 1-8) ===")
for phrase in ["open notepad", "launch notepad", "start notepad", "run notepad"]:
    check(f"app_{phrase}", phrase, "open_application")
for phrase in ["open calculator", "open vs code", "open file explorer", "open powershell"]:
    check(f"app_{phrase}", phrase, "open_application")

# ------------------------------------------------------------------ #
print("\n=== 2. APPLICATION DISCOVERY (tests 9-15) ===")
check("9_chrome",   "open chrome",   "open_application")
check("10_edge",    "open edge",     "open_application")
check("11_spotify", "open spotify",  "open_application")
check("12_discord", "open discord",  "open_application")
check("13_steam",   "open steam",    "open_application")
check("14_whatsapp","open whatsapp", "open_application")
check("15_vscode",  "open vscode",   "open_application")

# ------------------------------------------------------------------ #
print("\n=== 3. APPLICATION ALIASES (tests 16-22) ===")
check("16_google_chrome",    "open google chrome",        "open_application")
check("17_chrome",           "launch chrome",             "open_application")
check("18_start_chrome",     "start chrome",              "open_application")
check("19_vs_code",          "open vs code",              "open_application")
check("20_visual_studio",    "launch visual studio code", "open_application")
check("21_file_explorer",    "open file explorer",        "open_application")
check("22_explorer",         "open explorer",             "open_application")

# ------------------------------------------------------------------ #
print("\n=== 4. FOLDER ALIASES (tests 23-30) ===")
check("23_documents",      "open documents",          "open_folder")
check("24_my_documents",   "open my documents folder","open_folder")
check("25_downloads",      "open downloads",          "open_folder")
check("26_my_downloads",   "open my downloads folder","open_folder")
check("27_desktop",        "open desktop",            "open_folder")
check("28_my_desktop",     "open my desktop",         "open_folder")
check("29_spidy",          "open spidy",              "open_folder")
check("30_spidy_folder",   "open spidy folder",       "open_folder")

# ------------------------------------------------------------------ #
print("\n=== 5. FOLDER PATH SUPPORT (tests 31-33) ===")
check("31_explicit_spidy",  "open folder c:\\spidy",      "open_folder")
check("32_explicit_docs",   "open folder c:\\users\\pavan\\documents", "open_folder")
check("33_explicit_dl",     "open folder c:\\users\\pavan\\downloads", "open_folder")

# ------------------------------------------------------------------ #
print("\n=== 6. FOLDER SECURITY — must match list/open tool (actual block enforced at execute) ===")
check("34_windows_block",   "open folder c:\\windows",       "open_folder")
check("35_progfiles_block", "open folder c:\\program files", "open_folder")
check("36_list_windows",    "list files in c:\\windows",     "list_directory")
check("37_list_progfiles",  "list files in c:\\program files","list_directory")

# ------------------------------------------------------------------ #
print("\n=== 7. PATH TRAVERSAL SECURITY ===")
check("38_traversal_1", "open folder c:\\spidy\\..\\windows",         "open_folder")
check("39_traversal_2", "list files in c:\\spidy\\..\\windows",       "list_directory")
check("40_traversal_3", "open folder c:\\users\\pavan\\documents\\..\\..\\windows","open_folder")

# ------------------------------------------------------------------ #
print("\n=== 8. DIRECTORY LISTING (tests 41-45) ===")
check("41_list_spidy",      "list files in c:\\spidy",    "list_directory")
check("42_show_spidy",      "show files in c:\\spidy",    "list_directory")
check("43_whats_in",        "what's in c:\\spidy",        "list_directory")
check("44_list_docs",       "list my documents",          "list_directory")
check("45_show_downloads",  "show my downloads",          "list_directory")

# ------------------------------------------------------------------ #
print("\n=== 9. SYSTEM INFO (tests 46-50) ===")
check("46_sys_info",  "system info",                 "get_system_info")
check("47_sys_info2", "system information",          "get_system_info")
check("48_specs",     "my computer specs",           "get_system_info")
check("49_computer",  "show my computer information","get_system_info")
check("50_pc_specs",  "what are my pc specs",        "get_system_info")

# ------------------------------------------------------------------ #
print("\n=== 10. ACTIVE WINDOW (tests 51-53) ===")
check("51_active",  "active window",  "get_active_window")
check("52_current", "current window", "get_active_window")
check("53_whats_open","what's open",  "get_active_window")

# ------------------------------------------------------------------ #
print("\n=== 11-12. WINDOW MANAGEMENT (tests 54-59) ===")
check("54_min_notepad",  "minimize notepad",   "window_management")
check("55_max_notepad",  "maximize notepad",   "window_management")
check("56_close_notepad","close notepad",      "window_management")
check("57_close_vscode", "close vs code",      "window_management")

# ------------------------------------------------------------------ #
print("\n=== 13. CONFIRMATION SYSTEM (tests 60) ===")
check("60_open_folder_spidy","open folder c:\\spidy","open_folder")

# ------------------------------------------------------------------ #
print("\n=== 14. CASE INSENSITIVITY (tests 61-64) ===")
check("61_upper",  "OPEN NOTEPAD",  "open_application")
check("62_title",  "Open Notepad",  "open_application")
check("63_mixed",  "open NOTEPAD",  "open_application")
check("64_random", "OpEn NoTePaD",  "open_application")

# ------------------------------------------------------------------ #
print("\n=== 15. UNKNOWN REQUESTS (tests 65-67) ===")
check("65_nonsense",  "open something that doesnt exist", None)
check("66_random",    "do something random",             None)
check("67_gibberish", "xyz abc",                         None)

# ------------------------------------------------------------------ #
print("\n=== 17. BACKWARD COMPATIBILITY (tests 69-73) ===")
check("69_notepad",    "open notepad",        "open_application")
check("70_calc",       "open calculator",     "open_application")
check("71_vscode",     "open vs code",        "open_application")
check("72_explorer",   "open file explorer",  "open_application")
check("73_powershell", "open powershell",     "open_application")

# ------------------------------------------------------------------ #
print("\n=== EXECUTE TESTS: Security blocking (actual execute()) ===")
from tools.open_folder import OpenFolderTool
from tools.list_directory import ListDirectoryTool

ft = OpenFolderTool()
lt = ListDirectoryTool()

# Blocked paths
for path in ["C:\\Windows", "C:\\Program Files"]:
    res = ft.execute(target=path)
    if not res.success and ("denied" in res.message.lower() or "not allowed" in res.message.lower() or "not in" in res.message.lower()):
        print(f"  PASS [security_block] open_folder '{path}' -> BLOCKED")
        pass_count += 1
    else:
        print(f"  FAIL [security_block] open_folder '{path}' -> {res.message}")
        fail_count += 1

    res = lt.execute(target=path)
    if not res.success and ("denied" in res.message.lower() or "not allowed" in res.message.lower() or "not in" in res.message.lower()):
        print(f"  PASS [security_block] list_dir '{path}' -> BLOCKED")
        pass_count += 1
    else:
        print(f"  FAIL [security_block] list_dir '{path}' -> {res.message}")
        fail_count += 1

# Path traversal
for traversal in [r"C:\SPIDY\..\Windows", r"C:\Users\pavan\Documents\..\..\Windows"]:
    res = ft.execute(target=traversal)
    if not res.success:
        print(f"  PASS [traversal] open_folder '{traversal}' -> BLOCKED")
        pass_count += 1
    else:
        print(f"  FAIL [traversal] open_folder '{traversal}' -> allowed! {res.message}")
        fail_count += 1

    res = lt.execute(target=traversal)
    if not res.success:
        print(f"  PASS [traversal] list_dir '{traversal}' -> BLOCKED")
        pass_count += 1
    else:
        print(f"  FAIL [traversal] list_dir '{traversal}' -> allowed! {res.message}")
        fail_count += 1

# Nonexistent but allowed path
res = lt.execute(target=r"C:\SPIDY\nonexistent_xyz")
if not res.success and "not found" in res.message.lower():
    print(f"  PASS [error_handling] list_dir nonexistent -> useful error")
    pass_count += 1
else:
    print(f"  FAIL [error_handling] list_dir nonexistent -> {res.message}")
    fail_count += 1

# ------------------------------------------------------------------ #
print(f"\n{'='*50}")
print(f"RESULTS: {pass_count} PASSED  |  {fail_count} FAILED")
if fail_count == 0:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED — review above")
print(f"{'='*50}\n")
