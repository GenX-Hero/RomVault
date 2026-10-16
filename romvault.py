#!/usr/bin/env python3
"""
RomVault - Management and audit tool for ROMs in ES-DE.

pip install gspread is optional for this application to run
pip install py7zr is mandatory for this application to run
"""

# STANDARD LIBRARY IMPORTS
import os
import sys
import sqlite3
import datetime
import re
import html
import json
import math
import readline
import zipfile
import io
import shutil
import difflib
import hashlib
import zlib

# THIRD-PARTY IMPORTS
try:
    import gspread
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False

try:
    import py7zr
except ImportError:
    print("\n[!] CRITICAL ERROR: The mandatory 'py7zr' library is missing.")
    print("Please install it before running RomVault by executing:")
    print("    pip install py7zr\n")
    sys.exit(1)


# GLOBAL VARIABLES - DON'T TOUCH UNLESS YOU KNOW WHAT TO DO
SW_VERSION    = "1.0"
DB_FILE       = "romvault.db"
CONFIG_FILE   = "romvault.cfg"
ASCII_ART     = "romvault.art"
DB_MAP_RULES  = "romvault.map"
RES_TRANSLATE = "romvault.lng"
GAMELIST_FILE = "gamelist.xml"

# TRIAGE HEURISTIC SCORING CONFIGURATION
# | You can modify the weights or add new rules. The engine
# | will evaluate the regexes against the lowercase name.
# | IMPORTANT: Back up the file before experimenting.
DICT_SCORING_RULES = [
    # Absolute penalties for discards, hacks, and bad dumps
    {
        "pattern": (
            r'\[h.*?\]|\(hack\)|\[t-.*\]|\(beta\)|'
            r'\(proto\)|\(sample\)|\[b.*?\]'
        ),
        "weight": -2000},
    
    # Regions and languages ​​– Priority 1 <- YOU ARE ENCOURAGED TO SET YOURS
    {
        "pattern": r'\([^)]*\b(europe|italy|ita|it)\b[^)]*\)',
        "weight": 300,
    },
    
    # Regions - Priority 2 <- Different region than yours, though still relevant.
    {
        "pattern": r'\([^)]*\b(usa|world)\b[^)]*\)',
        "weight": 200,
    },
    
    # Regions - Priority 3 <- Regions you may want if you have nothing better.
    {
        "pattern": r'\([^)]*\b(japan|korea|asia)\b[^)]*\)',
        "weight": 50,
    },
    
    # Revision bonus: prioritizing the most up-to-date versions within the same region.
    {
        "pattern": r'rev|v1\.|bug fix',
        "weight": 20,
    },
]

# --- DON'T MODIFY BEYOND THIS POINT ---
# --- DON'T MODIFY BEYOND THIS POINT ---
# --- DON'T MODIFY BEYOND THIS POINT ---

# ANSI COLOR ESCAPE SEQUENCES - DON'T TOUCH
RED = '\033[91m'
YELLOW = '\033[93m'
CYAN = '\033[96m'
GREEN = '\033[92m'
MAGENTA = '\033[95m'
BOLD = '\033[1m'
RESET = '\033[0m'

# Dictionary mapping console systems to valid ROM file extensions
DICT_EXPECTED_EXTENSIONS = {
    # Nintendo
    "nes": [".nes"],
    "snes": [".sfc", ".smc", ".fig"],
    "snesna": [".sfc", ".smc", ".fig"],
    "sfc": [".sfc", ".smc", ".fig"],
    "gb": [".gb"],
    "gbc": [".gbc"],
    "gba": [".gba"],
    "n64": [".n64", ".z64", ".v64"],
    "virtualboy": [".vb"],
    "fds": [".fds"],
    # Sega
    "mastersystem": [".sms"],
    "megadrive": [".md", ".smd", ".gen", ".bin"],
    "genesis": [".md", ".smd", ".gen", ".bin"],
    "gamegear": [".gg"],
    "sega32x": [".32x"],
    "sg-1000": [".sg"],
    # Atari
    "atari2600": [".a26", ".bin"],
    "atari5200": [".a52", ".bin"],
    "atari7800": [".a78", ".bin"],
    "atarilynx": [".lnx"],
    "atarijaguar": [".j64", ".jag"],
    # NEC & Others
    "pcengine": [".pce"],
    "supergrafx": [".sgx"],
    "wonderswan": [".ws"],
    "wonderswancolor": [".wsc"],
    "ngp": [".ngp"],
    "ngpc": [".ngc"],
    "colecovision": [".col"],
    "intellivision": [".int"],
    "vectrex": [".vec"]
}

# LOAD CONFIGURATION - DON'T TOUCH
if not os.path.exists(CONFIG_FILE):
    os.system('clear' if os.name == 'posix' else 'cls')
    print(
        f"{RED}Critical Error{RESET}: Configuration file '{CONFIG_FILE}' not "
        "found.\nPlease download or create a basic configuration  file and "
        "customize it for your\ninstallation. Refer to Chapter 1 of the setup "
        "manual, \"Setting up RomVault\"."
    )
    sys.exit(1)

try:
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
        VAR_ROMS_DIR = config_data.get("VAR_ROMS_DIR", "")
        VAR_GAMELIST_DIR = config_data.get("VAR_GAMELIST_DIR", "")
        VAR_INCOMING_DIR = config_data.get("VAR_INCOMING_DIR", "")
        VAR_REPORT_DIR = config_data.get("VAR_REPORT_DIR", "")
        VAR_HIDDEN_MULTI = config_data.get("VAR_HIDDEN_MULTI", ".multidisc")
        VAR_GSHEET_EXPORT = config_data.get("VAR_GSHEET_EXPORT", "")
        VAR_GSHEET_NAME = config_data.get("VAR_GSHEET_NAME", "")
        CURRENT_LANG = config_data.get("LANGUAGE", "it").lower()
except Exception as e:
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{RED}Critical Error{RESET}: Failed to parse '{CONFIG_FILE}':\n-> {e}")
    sys.exit(1)

# LOAD LANGUAGE FILE - DON'T TOUCH
if not os.path.exists(RES_TRANSLATE):
    os.system('clear' if os.name == 'posix' else 'cls')
    print(
        f"{RED}Critical Error{RESET}: Language file '{RES_TRANSLATE}' not "
        "found.\nPlease download the official language definitions package "
        "from the repository.\nRefer to Chapter 1 of the setup manual, \"Setting "
        "up RomVault.\""
    )
    sys.exit(1)

try:
    with open(RES_TRANSLATE, 'r', encoding='utf-8') as f:
        LANG_DATA = json.load(f)
except Exception as e:
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{RED}Critical Error{RESET}: Failed to parse '{RES_TRANSLATE}':\n-> {e}")
    sys.exit(1)


# TRANSLATION ENGINE - DON'T TOUCH
def tr(key_path):
    """
    Utility: Translation engine:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None
    
    Retrieves the translated string using a dot-notation key (e.g., 'menu.opt1'). 
    Implements automatic fallback to Italian ('it') if the key is missing in the
    selected language.
    ---
    Parameters: 'key_path' Dot-notation string representing the translation key.

    Returns:    'str' The localized translation string, or a placeholder if missing.
    """
    keys = key_path.split('.')
    
    # Attempt using the language selected in the configuration file
    current_dict = LANG_DATA.get(CURRENT_LANG, {})
    for k in keys:
        if isinstance(current_dict, dict) and k in current_dict:
            current_dict = current_dict[k]
        else:
            current_dict = None
            break
            
    if current_dict is not None:
        return current_dict

    # Fallback to Italian ('it') if the key is not found.
    fallback_dict = LANG_DATA.get('it', {})
    for k in keys:
        if isinstance(fallback_dict, dict) and k in fallback_dict:
            fallback_dict = fallback_dict[k]
        else:
            return f"[{key_path}]" # Placeholder visible if completely missing 
            
    return fallback_dict


def trf(key_path, **kwargs):
    """
    Utility: Formatted Translation engine:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Retrieves the translated string, applies ANSI color formatting, and 
    automatically resolves global script variables (e.g. {DB_FILE}) along 
    with any custom keyword arguments.
    ---
    Parameters: 'key_path' Dot-notation string representing the translation key.
                '**kwargs' Optional keyword arguments and color overrides.
                    
    Returns:    'str' The fully formatted and localized translation string.
    """
    str_text = tr(key_path)
    
    color_map = {
        "yellow": '\033[93m',
        "red": '\033[91m',
        "green": '\033[92m',
        "cyan": '\033[96m',
        "reset": '\033[0m'
    }
    
    # It combines script's global variables, colors, and any override on the fly.
    fmt_args = {**globals(), **color_map, **kwargs}
    
    try:
        return str_text.format(**fmt_args)
    except KeyError:
        return str_text
# END OF TRANSLATION ENGINE


def util_clean_screen(menuitem=None):
    """
    Utility : Clean screen:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None
    
    Called to clear the screen, redraw the ASCII art logo, and the contextual
    menu header.
    ---
    Parameter:  'menuitem' receive the menu item number to pass to the 
                    util_draw_menu_header to draw the proper contextual
                    header.
    Returns:    Nothing
    """
    os.system('clear' if os.name == 'posix' else 'cls')
    util_draw_header()
    util_draw_menu_header(menuitem)


def util_draw_header():
    """
    Utility: Draw header:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    This utility function draws an ASCII art header on a cleared screen, by 
    reading the external file, stored in the ASCII_ART variable; if the file
    does not exist or is corrupted, the exception block generates a simple
    text-based fallback header. ASCII art is limited to 80 columns for
    generic terminal compatibility - ERROR SEVERITY = 0 Non blocking.
    ---
    Parameter:  None
    
    Returns:    Nothing
    """
    try:
        # Read the ASCII art file 
        with open(ASCII_ART, 'r', encoding='utf-8') as f:
            ascii_art = f.read()
        ascii_art = ascii_art.replace('\\033', '\033')
        print(ascii_art.strip())
        testo_destra = f"RomVault v.{SW_VERSION} - By GenX-Hero & Gemini"
        print(f"{YELLOW}{testo_destra:>80}{RESET}")
        print(f"{CYAN}{'-'*80}{RESET}")

    except FileNotFoundError:
        # 80 columns fallback title.
        print(f"{CYAN}{'='*80}{RESET}")
        text = f" RomVault v.{SW_VERSION} - By GenX-Hero & Gemini "
        inner_width = 80 - 2
        centered_content = text.center(inner_width, ' ')
        fallback_line = f"{CYAN}={RED}{BOLD}{centered_content}{CYAN}={RESET}"
        print(fallback_line)
        print(f"{CYAN}{'='*80}{RESET}")


def util_draw_menu_header(menuitem=None):
    """
    Utility: Draw menu header:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Draw contextual menu-header.
    ---
    Parameter: 'menuitem' receive the menu item number to draw the
                    proper contextual header.
    Returns:    Nothing
    """
    testo = ""
    match menuitem:
        case 1:
            testo = trf('menu.item_1')
        case 2:
            testo = trf('menu.item_2')
        case 3:
            testo = trf('menu.item_3')
        case 4:
            testo = trf('menu.item_4')
        case 21:
            testo = trf('menu.item_21')
        case 22:
            testo = trf('menu.item_22')
        case 41:
            testo = trf('menu.item_41')
        case 42:
            testo = trf('menu.item_42')
        case 43:
            testo = trf('menu.item_43')
        case _:
            testo = trf('menu.item_0')

    inner_width = 80
    centered_content = testo.center(inner_width, ' ')
    menu_line = f"{centered_content}"
    print(f"{GREEN}{BOLD}{menu_line}{RESET}")
    print(f"{CYAN}{'-'*80}{RESET}\n")


def util_error_display(room, err_type, msg_indexes, direction="fwd"):
    """
    Utility: Display error and warning messages:
    v.2.0 Completion status 100%
    Multilanguage support 100%
    TO DO: TEST OUT and DEBUG Improveable

    Manage error/warning unified center:
    Stubbed in this release, needs revision.
    ---
    Parameters: room: Room ID (es. 43) used to inject clearscreen parameter.
                err_type    : "W" (warning) or "E" (error) for the message prefix.
                msg_indexes : List of message idx (es. 1, 2, 3) to build the output.
                direction   : "fwd" exit message to go ahead.
                              "bck" exit message to return.
    Returns   : Nothing
    """
    # 1. Clean screen and show room number
    util_clean_screen(room)
    print()
    
    # 2. Map room number with json language's block identifier.
    room_map = {
        43: "triage",
        41: "crosscheck"
        # Add here more rooms while refactoring
    }
    
    type_map = {
        "W": "warning",
        "E": "error"
    }
    
    section = room_map.get(room, "triage")
    prefix = type_map.get(err_type, "warning")
    
    # 3. Cycle indexes, build the key (es. triage.warning1), print out with trf()
    for idx in msg_indexes:
        key_path = f"{section}.{prefix}{idx}"
        print(f" {trf(key_path)}")
        
    print("\n")
    
    # 4. Footer interattivo
    if direction == "fwd":
        input(f" {trf('generic.press_enter')}")
    elif direction == "bck":
        input(f" {trf('generic.press_back')}")
        
    return None


def util_xml_scan(str_emulator):
    """
    Utility: XML Scanner:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Given a system abbreviation following the ES-DE standard (gba, snes, ps2,
    etc.), it scans the gamelist.xml file, retrieving the total count of ROMs
    (<game> tags), the     count of hidden ROMs (<hidden> tags), and the complete
    list of filenames (<path> tags).
    ---
    Parameter:  'str_emulator' emulation system for retrieving information
                    
    Returns:    'roms_listed' Count of total ROMs for the system under analysis.
                'roms_hidden' Count of total hidden ROMs for the system under analysis.
                'roms_files' Set of all ROMs for the system under analysis
    """
    xml_gamelist = os.path.join(VAR_GAMELIST_DIR, str_emulator, GAMELIST_FILE)
    roms_listed = 0
    roms_hidden = 0
    roms_files = set()

    if not os.path.exists(xml_gamelist):
        return roms_listed, roms_hidden, roms_files

    try:
        with open(xml_gamelist, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()

        # Get and cycle all listed ROMs
        games = re.findall(r'<game>(.*?)</game>', content, re.DOTALL)
        roms_listed = len(games)

        for game_block in games:
            # Count all hidden ROMs in the subset
            if re.search(r'<hidden>\s*true\s*</hidden>', game_block, re.IGNORECASE):
                roms_hidden += 1
            # Get all ROMs' archive name and push it into the returning array
            match_path = re.search(r'<path>(.*?)</path>', game_block, re.IGNORECASE)
            if match_path:
                # ES-DE typically saves roms' filesa "./rom.zip", 
                # we strip off the path part to get only "rom.zip"
                p = html.unescape(match_path.group(1).strip())
                roms_files.add(os.path.basename(p))
    
    except Exception:
        pass

    return roms_listed, roms_hidden, roms_files


def util_pre_compiled_input(str_prompt, str_prefill=''):
    """
    Utility: Pre-compiled Input Prompt:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Displays an input prompt pre-filling the readline buffer with a string,
    allowing the user to edit it without rewriting it from scratch.
    ---
    Parameters: 'str_prompt' The text prompt displayed to the user.
                'str_prefill' The default text string to pre-load into the buffer.
                    
    Returns:    'str' The user input string read from standard input.
    """
    readline.set_startup_hook(lambda: readline.insert_text(str_prefill))
    try:
        return input(str_prompt)
    finally:
        # Cleans the hook to avoid future inputs' contaminations
        readline.set_startup_hook()


def util_cartridge_system_choice(cursor):
    """
    Utility: Cartridge System Choice:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Extracts only 'cartridge'-type systems from the database (matching items in
    DICT_EXPECTED_EXTENSIONS) that actually contain records, displaying them in
    a single clean screen.
    ---
    Parameter:  'cursor' SQLite database cursor object for query execution.
                    
    Returns:    'str' The selected system name string, or None if cancelled.
    """
    # Fetch all emulators from database.
    cursor.execute("SELECT DISTINCT sistema FROM roms ORDER BY sistema")
    lst_all_systems = [row[0] for row in cursor.fetchall()]
    
    # Cycle to filter only those in the cartridge dictionary.
    lst_cartridge_systems = [
        s for s in lst_all_systems 
        if s.lower() in DICT_EXPECTED_EXTENSIONS
    ]
    
    if not lst_cartridge_systems:
        util_error_display(43, "W", (1, 2, 3, 4), "fwd")
        return None

    int_cartridge_systems_count = len(lst_cartridge_systems)

    while True:
        util_clean_screen(43)

        # Print 3 columns' grid
        num_rows = math.ceil(int_cartridge_systems_count / 3)
        for r in range(num_rows):
            row_str = ""
            for c in range(3):
                idx = (r * 3) + c
                if idx < int_cartridge_systems_count:
                    global_idx = idx + 1
                    sys_name = lst_cartridge_systems[idx]
                    sys_disp = sys_name[:18]
                    item_str = f"[{global_idx:>2}] {sys_disp}"
                    row_str += f"{item_str:<26}"
            print(row_str)

        print()
        print(f"{CYAN}[X] {trf('utility.cartridge_systems.cancel_option')}{RESET}")
        print()
        
        str_choice = input(trf(
            'utility.cartridge_systems.make_a_choice',
            int_cartridge_systems_count=int_cartridge_systems_count
        )).strip().upper()

        if str_choice == 'X':
            return None
        elif str_choice.isdigit():
            idx_choice = int(str_choice)
            if 1 <= idx_choice <= int_cartridge_systems_count:
                return lst_cartridge_systems[idx_choice - 1]
            else:
                print(trf(
                    'utility.cartridge_systems.err_invalid_choice',
                    int_cartridge_systems_count=int_cartridge_systems_count
                ))
                input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        else:
            print(f"{RED}{trf('generic.invalid_command')}{RESET}")
            input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")


def util_normalize_filename(filename):
    """
    Utility: Filename normalization and cleaning engine:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Removes file extensions, bracketed tags, handles camelCase/attached 
    numbers, strips special characters, and normalizes Roman numerals 
    to generate a clean base title for comparisons.
    ---
    Parameters:  'filename' String representing the filename or title to normalize.
                    
    Returns:    'str' The cleaned, lowercased, and normalized base title string.
    """
    # Remove any trailing extensions (e.g. .zip, .7z, .gba, .ws, .wsc, etc.)
    title = re.sub(r'\.[a-zA-Z0-9]+$', '', filename)
    
    # Remove contents inside parentheses and square brackets (e.g. (USA), [b])
    title = re.sub(r'\(.*?\)|\[.*?\]', '', title)
    
    # Separate camelCase or letters attached to numbers (e.g. sonicIII -> sonic III)
    title = re.sub(r'([a-z])([A-Z0-9])', r'\1 \2', title)
    
    # Clean special characters and convert to lowercase
    title = re.sub(r'[^a-z0-9\s]', ' ', title.lower())
    
    # Isolated Roman numerals translation map
    roman_map = {
        'i': '1', 'l': '1', 'ii': '2', 'll': '2', 'iii': '3', 'lll': '3',
        'iv': '4', 'v': '5', 'vi': '6', 'vii': '7', 'viii': '8', 'ix': '9', 'x': '10'
    }
    
    words = title.split()
    normalized_words = [roman_map.get(w, w) for w in words]
    
    # Recompose with single spaces and strip excess whitespace
    return " ".join(normalized_words).strip()


def util_analyze_archive(str_file_path, str_system):
    """
    Utility: Compressed archive validation and analysis engine:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Centralized function for analyzing compressed archives (.zip and .7z).
    Requires py7zr as a mandatory dependency. Validates contents against 
    expected extensions and calculates MD5/CRC32 hashes in streaming.
    ---
    Parameters:  'str_file_path' String representing the archive file path.
                 'str_system'    String representing the target system name.
                    
    Returns:    'dict' Dictionary containing validation results, counts, hashes,
                           and reasons.
    """
    dict_result = {
        "file_ok": False,
        "file_count": 0,
        "internal_filename": "",
        "crc32": "",
        "md5": "",
        "archive_norm_title": "",
        "internal_norm_title": "",
        "motivo": ""
    }

    if not os.path.exists(str_file_path):
        dict_result["motivo"] = trf(
            'utility.archive_analysis.err_not_found', 
            path=str_file_path)
        return dict_result

    str_system_lower = str_system.lower()
    if str_system_lower not in DICT_EXPECTED_EXTENSIONS:
        dict_result["motivo"] = trf(
            'utility.archive_analysis.err_system_not_configured', 
            system=str_system)
        return dict_result

    list_valid_extensions = DICT_EXPECTED_EXTENSIONS[str_system_lower]
    str_base_filename = os.path.basename(str_file_path)
    dict_result["archive_norm_title"] = util_normalize_filename(str_base_filename)

    str_archive_ext = os.path.splitext(str_file_path)[1].lower()

    # --- 1. ZIP ARCHIVES HANDLING ---
    if str_archive_ext == '.zip':
        try:
            with zipfile.ZipFile(str_file_path, 'r') as zf:
                list_infolist = [i for i in zf.infolist() if not i.is_dir()]
                dict_result["file_count"] = len(list_infolist)

                if not list_infolist:
                    dict_result["motivo"] = trf(
                        'utility.archive_analysis.err_empty_zip')
                    return dict_result
                
                if any(
                    info.filename.lower().endswith('.xml')
                    for info in list_infolist
                ):
                    dict_result["motivo"] = trf(
                        'utility.archive_analysis.err_xml_not_allowed')
                    return dict_result

                obj_main_file = max(list_infolist, key=lambda i: i.file_size)
                _, str_inner_ext = os.path.splitext(obj_main_file.filename.lower())

                if str_inner_ext not in list_valid_extensions:
                    dict_result["motivo"] = trf(
                        'utility.archive_analysis.err_unexpected_ext', 
                        ext=str_inner_ext, system=str_system
                    )
                    return dict_result

                dict_result["internal_filename"] = obj_main_file.filename
                dict_result["internal_norm_title"] = util_normalize_filename(
                    obj_main_file.filename)

                with zf.open(obj_main_file) as f_inner:
                    str_md5_hex, str_crc32_hex = util_calc_multiple_hashes_from_stream(
                        f_inner)

                dict_result["crc32"] = str_crc32_hex
                dict_result["md5"] = str_md5_hex
                dict_result["file_ok"] = True

        except zipfile.BadZipFile:
            dict_result["motivo"] = trf('utility.archive_analysis.err_bad_zip')
        except Exception as e:
            dict_result["motivo"] = trf(
                'utility.archive_analysis.err_read_zip', error=str(e))

    # --- 2. 7Z ARCHIVES HANDLING ---
    elif str_archive_ext == '.7z':
        try:
            with py7zr.SevenZipFile(str_file_path, mode='r') as archive:
                list_file_infos = archive.list()
                list_valid_infos = [
                    info for info in list_file_infos if not info.is_directory]
                dict_result["file_count"] = len(list_valid_infos)

                if not list_valid_infos:
                    dict_result["motivo"] = trf(
                        'utility.archive_analysis.err_empty_7z')
                    return dict_result

                if any(
                    info.filename.lower().endswith('.xml')
                    for info in list_valid_infos
                ):
                    dict_result["motivo"] = trf(
                        'utility.archive_analysis.err_xml_not_allowed')
                    return dict_result

                obj_main_info = max(list_valid_infos, key=lambda i: i.uncompressed)
                _, str_inner_ext = os.path.splitext(obj_main_info.filename.lower())

                if str_inner_ext not in list_valid_extensions:
                    dict_result["motivo"] = trf(
                        'utility.archive_analysis.err_unexpected_ext', 
                        ext=str_inner_ext, system=str_system)
                    return dict_result

                dict_result["internal_filename"] = obj_main_info.filename
                dict_result["internal_norm_title"] = util_normalize_filename(
                    obj_main_info.filename)

                dict_extracted = archive.read([obj_main_info.filename])
                if obj_main_info.filename in dict_extracted:
                    bytes_stream_data = dict_extracted[obj_main_info.filename]
                    obj_stream_io = (
                        io.BytesIO(bytes_stream_data) 
                        if isinstance(bytes_stream_data, bytes)
                        else bytes_stream_data
                    )

                    str_md5_hex, str_crc32_hex = util_calc_multiple_hashes_from_stream(
                        obj_stream_io)
                    dict_result["crc32"] = str_crc32_hex
                    dict_result["md5"] = str_md5_hex
                    dict_result["file_ok"] = True
                else:
                    dict_result["motivo"] = trf(
                        'utility.archive_analysis.err_extract_7z')

        except Exception as e:
            dict_result["motivo"] = trf(
                'utility.archive_analysis.err_read_7z', error=str(e))

    else:
        dict_result["motivo"] = trf(
            'utility.archive_analysis.err_unsupported_format', 
            ext=str_archive_ext)

    return dict_result


def util_calc_rom_score(str_game_name):
    """
    Utility: ROM Heuristic Score calculator:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Assigns a heuristic score to the ROM by evaluating the rules defined 
    in the global variable DICT_SCORING_RULES.
    ---
    Parameters:  'str_game_name' String representing the game name or filename.
                    
    Returns:    'int' Calculated heuristic score integer value.
    """
    int_score = 1000
    str_name_lower = str_game_name.lower()
    
    for dict_rules in DICT_SCORING_RULES:
        if re.search(dict_rules["pattern"], str_name_lower):
            int_score += dict_rules["weight"]
            
    return int_score


def util_calc_md5_rom_from_file(str_file_path):
    """
    Utility: Calculate ROM MD5 from file:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Calculates the MD5 hash by reading blocks from a filesystem file.
    ---
    Parameters:  'str_file_path' String representing the target file path.
                    
    Returns:    'str' MD5 hash formatted as a 32-character hexadecimal string.
    """
    obj_hash_md5 = hashlib.md5()
    
    with open(str_file_path, "rb") as obj_file:
        for chunk in iter(lambda: obj_file.read(4096), b""):
            obj_hash_md5.update(chunk)
            
    return obj_hash_md5.hexdigest()


def util_calc_md5_rom_from_stream(obj_file_stream):
    """
    Utility: Calculate ROM MD5 from stream:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Calculates the MD5 hash by reading blocks from a data stream in memory.
    ---
    Parameters:  'obj_file_stream' File stream object to read from.
                    
    Returns:    'str' MD5 hash formatted as a 32-character hexadecimal string.
    """
    obj_hash_md5 = hashlib.md5()
    
    for chunk in iter(lambda: obj_file_stream.read(4096), b""):
        obj_hash_md5.update(chunk)
            
    return obj_hash_md5.hexdigest()


def util_calc_crc32_rom_from_file(str_file_path):
    """
    Utility: Calculate ROM CRC32 from file:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Calculates the physical CRC32 by reading blocks from a filesystem file.
    ---
    Parameters:  'str_file_path' String representing the target file path.
                    
    Returns:    'str' CRC32 hash formatted as an 8-character uppercase hexadecimal string.
    """
    int_crc_value = 0
    
    with open(str_file_path, "rb") as obj_file:
        for chunk in iter(lambda: obj_file.read(4096), b""):
            int_crc_value = zlib.crc32(chunk, int_crc_value)
            
    return f"{int_crc_value & 0xFFFFFFFF:08X}"


def util_calc_crc32_rom_from_stream(obj_file_stream):
    """
    Utility: Calculate ROM CRC32 from stream:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Calculates the physical CRC32 by reading data stream blocks.
    ---
    Parameters:  'obj_file_stream' File stream object to read from.
                    
    Returns:    'str' CRC32 hash formatted as an 8-character uppercase hexadecimal string.
    """
    int_crc_value = 0
    
    for chunk in iter(lambda: obj_file_stream.read(4096), b""):
        int_crc_value = zlib.crc32(chunk, int_crc_value)
        
    return f"{int_crc_value & 0xFFFFFFFF:08X}"


def util_calc_multiple_hashes_from_file(str_file_path):
    """
    Utility: Calculate multiple ROM hashes from file:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Simultaneously calculates MD5 and CRC32 by reading the physical file once.
    Optimized for large files to reduce disk I/O.
    ---
    Parameters:  'str_file_path' String representing the target file path.
                    
    Returns:    'tuple' A tuple containing (str_md5_hex, str_crc32_hex).
    """
    obj_hash_md5 = hashlib.md5()
    int_crc_value = 0
    
    with open(str_file_path, "rb") as obj_file:
        for chunk in iter(lambda: obj_file.read(4096), b""):
            obj_hash_md5.update(chunk)
            int_crc_value = zlib.crc32(chunk, int_crc_value)
            
    str_crc32_hex = f"{int_crc_value & 0xFFFFFFFF:08X}"
    return obj_hash_md5.hexdigest(), str_crc32_hex


def util_calc_multiple_hashes_from_stream(obj_file_stream):
    """
    Utility: Calculate multiple ROM hashes from stream:
    v.1.0 Completion status 100%
    Multilanguage support 100% None
    TO DO: None

    Simultaneously calculates MD5 and CRC32 by reading data stream blocks once.
    Optimized to maximize performance by avoiding multiple extractions or reads.
    ---
    Parameters:  'obj_file_stream' File stream object to read from.
                    
    Returns:    'tuple' A tuple containing (str_md5_hex, str_crc32_hex).
    """
    obj_hash_md5 = hashlib.md5()
    int_crc_value = 0
    
    for chunk in iter(lambda: obj_file_stream.read(4096), b""):
        obj_hash_md5.update(chunk)
        int_crc_value = zlib.crc32(chunk, int_crc_value)
            
    str_crc32_hex = f"{int_crc_value & 0xFFFFFFFF:08X}"
    return obj_hash_md5.hexdigest(), str_crc32_hex


def oper_database_check():
    """
    Database Check & Self-Healing Engine
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Verifies the integrity of the SQLite database and table structure, comparing
    it dynamically with the fields defined in romvault.map.
    Handles automatic backup and recreation if corruption or schema mismatch occurs.
    ---
    Parameters:   None
    Returns:      None
    """
    util_clean_screen(1)

    print(f"{YELLOW}{trf('dbcheck.start_check')}{RESET}\n")

    # 1. Load mapping to know the desired structure
    try:
        with open(DB_MAP_RULES, 'r', encoding='utf-8') as f_map:
            list_mapping = json.load(f_map)
    except FileNotFoundError:
        str_err_msg = trf('dbcheck.map_not_found')
        print(f"{RED}{str_err_msg}{RESET}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return
    except json.JSONDecodeError as exc_json:
        str_err_msg = trf('dbcheck.map_json_error', error=exc_json)
        print(f"{RED}{str_err_msg}{RESET}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    dict_type_to_sql = {
        "string": "TEXT", "integer": "INTEGER", "boolean": "INTEGER",
    }
    set_expected_cols = {
        "id", "sistema", "last_scanned", "zipchk",
        "crc32", "md5", "internal_filename",
    }

    for dict_field in list_mapping:
        set_expected_cols.add(dict_field["db_column"])

    bool_db_exists = os.path.exists(DB_FILE)

    # Internal helper to create the table with real-time outputs
    def create_fresh_table(cursor_obj):
        list_cols_def = [
            "id INTEGER PRIMARY KEY AUTOINCREMENT", 
            "sistema TEXT",
            "zipchk INTEGER DEFAULT 0",
            "crc32 TEXT",
            "md5 TEXT",
            "internal_filename TEXT"
        ]
        for dict_field in list_mapping:
            str_col_name = dict_field["db_column"]
            str_col_type = dict_type_to_sql.get(dict_field["type"], "TEXT")
            list_cols_def.append(f"{str_col_name} {str_col_type}")
        list_cols_def.append("last_scanned DATETIME")

        str_create_query = (
            f"CREATE TABLE roms (\n    {',\n    '.join(list_cols_def)}\n)"
        )
        cursor_obj.execute(str_create_query)
        
        print(f"{GREEN}[OK] {trf('dbcheck.pragma_ok')}{RESET}")
        print(f"{GREEN}[OK] {trf('dbcheck.table_created')}{RESET}")

    try:
        if not bool_db_exists:
            print(f"{YELLOW}[INFO] {trf('dbcheck.db_not_found')}{RESET}")
            print(f"{GREEN}[OK] {trf('dbcheck.db_created')}{RESET}")
            conn_db = sqlite3.connect(DB_FILE)
            cursor_db = conn_db.cursor()
            create_fresh_table(cursor_db)
            conn_db.commit()
            conn_db.close()
        else:
            print(f"{GREEN}[OK] {trf('dbcheck.db_found')}{RESET}")
            
            # Attempt connection and checks on existing DB with real-time
            # corruption handling
            try:
                conn_db = sqlite3.connect(DB_FILE)
                cursor_db = conn_db.cursor()

                cursor_db.execute("PRAGMA integrity_check;")
                tuple_integrity = cursor_db.fetchone()
                if not tuple_integrity or tuple_integrity[0].lower() != "ok":
                    str_error_detail = (
                        tuple_integrity[0] 
                        if tuple_integrity 
                        else 'Unknown'
                    )
                    raise sqlite3.DatabaseError(
                        f"Integrity check failed: {str_error_detail}"
                    )

                print(f"{GREEN}[OK] {trf('dbcheck.pragma_ok')}{RESET}")

                cursor_db.execute("PRAGMA table_info(roms);")
                list_existing_cols_info = cursor_db.fetchall()

                bool_table_exists = len(list_existing_cols_info) > 0
                bool_schema_mismatch = False

                if bool_table_exists:
                    set_existing_cols = {col[1] for col in list_existing_cols_info}
                    if set_existing_cols != set_expected_cols:
                        bool_schema_mismatch = True
                        print(
                            f"{YELLOW}[WARNING] "
                            f"{trf('dbcheck.table_mismatch')}{RESET}"
                        )
                        print(
                            f"{YELLOW}[WARNING] "
                            f"{trf('dbcheck.table_drop')}{RESET}"
                        )
                        cursor_db.execute("DROP TABLE roms;")

                if not bool_table_exists or bool_schema_mismatch:
                    create_fresh_table(cursor_db)
                else:
                    print(f"{GREEN}[OK] {trf('dbcheck.table_aligned')}{RESET}")

                conn_db.commit()
                conn_db.close()

            except (sqlite3.Error, Exception) as exc_db:
                if 'conn_db' in locals() and conn_db:
                    try:
                        conn_db.close()
                    except:
                        pass
                
                str_broken_backup = f"{DB_FILE}.broken"
                if os.path.exists(DB_FILE):
                    shutil.copy2(DB_FILE, str_broken_backup)
                    os.remove(DB_FILE)

                str_err_msg = trf('dbcheck.db_sqlite_error', error=exc_db)
                print(f"{RED}[ERRORE] {str_err_msg}{RESET}")
                str_backup_msg = trf('dbcheck.db_backup_info', 
                                    broken_backup=str_broken_backup)
                print(f"{YELLOW}[INFO] {str_backup_msg}{RESET}")
                print(f"{GREEN}[OK] {trf('dbcheck.db_created')}{RESET}")

                conn_db = sqlite3.connect(DB_FILE)
                cursor_db = conn_db.cursor()
                create_fresh_table(cursor_db)
                conn_db.commit()
                conn_db.close()

    except Exception as exc_unexpected:
        str_unexp_msg = trf('dbcheck.unexpected_error', error=exc_unexpected)
        print(f"{RED}[ERRORE] {str_unexp_msg}{RESET}")

    print(f"\n{CYAN}{trf('dbcheck.check_completed')}{RESET}")
    input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")


def menu_db_manager():
    """
    Menu DB Manager:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Submenu: Advanced ROMs Management
    Draw the submenu.
    ---
    Parameter:  None
    
    Returns:    Nothing
    """
    while True:
        util_clean_screen(4)
        print(f"{GREEN} 1 {RESET}- {trf('menu.item_21')}")
        print(f"{GREEN} 2 {RESET}- {trf('menu.item_22')}")
        print(f"{RED} X {RESET}- {trf('menu.item_back')}")
        print()
        
        # input case-insensitive (x o X)
        input_choice = util_pre_compiled_input(
            f"{CYAN}{trf('generic.prompt_select')}{RESET}", "1"
        ).strip().upper()
        print()

        match input_choice:
            case '1':
                oper_incr_db_population()
            case '2':
                oper_full_db_population()
            case '3':
                oper_triage_roms()
            case 'X':
                # Leave this submenu and go back to the main.
                break
            case _:
                print(f"{RED}{trf('generic.invalid_command')}{RESET}")
                input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")


def oper_incr_db_population(menuitem=21):
    """
    Incremental Rom Update:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Performs incremental update by calculating the Δ between gamelist.xml files
    and the database. Manages insertions, metadata updates, and orphan record
    deletions.
    If called with an empty DB, Δ is the whole collection, so perform a full
    repopulation and not just incremental.
    ---
    Parameter:  'menuitem' What to show in menubar if called directly 21 if
                called by fullreset 22, defaults to 21.
    
    Returns:    Nothing
    """
    util_clean_screen(menuitem)
    if menuitem == 21:
        print(f"{YELLOW}{trf('dbmanager.just_incre_init')}{RESET}")
        print(f"{CYAN}{trf('dbmanager.scanning_delta')}{RESET}\n")
    elif menuitem == 22:
        print(f"{YELLOW}{trf('dbmanager.deep_clean_init')}{RESET}")
        print(f"{CYAN}{trf('dbmanager.total_delta')}{RESET}\n")

    if not os.path.exists(DB_FILE):
        str_db_msg = trf('dbmanager.db_not_found')
        print(f"\n{RED}{str_db_msg}{RESET}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    try:
        with open('romvault.map', 'r', encoding='utf-8') as f_map:
            list_mapping = json.load(f_map)
    except Exception as exc_map:
        str_map_err = trf('dbmanager.map_error', error=exc_map)
        print(f"\n{RED}{str_map_err}{RESET}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    try:
        conn_db = sqlite3.connect(DB_FILE)
        cursor_db = conn_db.cursor()

        str_now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        int_systems_affected = 0
        int_total_inserted = 0
        int_total_updated = 0
        int_total_deleted = 0

        list_mapped_cols = [dict_field["db_column"] for dict_field in list_mapping]
        
        if os.path.exists(VAR_GAMELIST_DIR):
            for str_system_folder in os.listdir(VAR_GAMELIST_DIR):
                str_system_path = os.path.join(VAR_GAMELIST_DIR, str_system_folder)
                str_xml_path = os.path.join(str_system_path, "gamelist.xml")

                if (
                    not os.path.isdir(str_system_path)
                    or str_system_folder.startswith('.')
                    or str_system_folder.lower() == 'cleanup'
                    or not os.path.exists(str_xml_path)
                ):
                    continue

                # --- 1. CURRENT DB STATE EXTRACTION ---
                str_query_select = (
                    f"SELECT filename, {', '.join(list_mapped_cols)}"
                    " FROM roms WHERE sistema = ?"
                )
                cursor_db.execute(str_query_select, (str_system_folder,))
                list_db_rows = cursor_db.fetchall()
                
                dict_db_data = {}
                for row_item in list_db_rows:
                    str_filename = row_item[0]
                    dict_db_data[str_filename] = dict(
                        zip(list_mapped_cols, row_item[1:])
                    )

                # --- 2. DESIRED XML STATE EXTRACTION ---
                dict_xml_data = {}
                with open(
                    str_xml_path, 'r', encoding='utf-8', errors='ignore'
                ) as f_xml:
                    str_content = f_xml.read()

                list_games = re.findall(
                    r'<game>(.*?)</game>', str_content, re.DOTALL
                )

                for str_game_block in list_games:
                    match_path = re.search(
                        r'<path>(.*?)</path>', str_game_block, re.IGNORECASE
                    )
                    if not match_path:
                        continue
                    
                    str_raw_path = html.unescape(match_path.group(1).strip())
                    str_xml_filename = os.path.basename(str_raw_path)
                    
                    dict_game_parsed = {}
                    for dict_field in list_mapping:
                        str_column = dict_field["db_column"]
                        str_tag = dict_field["xml_tag"]
                        str_type = dict_field["type"]

                        match_tag = re.search(
                            rf'<({str_tag})>(.*?)</\1>',
                            str_game_block,
                            re.IGNORECASE | re.DOTALL,
                        )
                        str_raw_value = (
                            match_tag.group(2).strip()
                            if match_tag
                            else None
                        )

                        if str_type == "boolean":
                            dict_game_parsed[str_column] = (
                                1
                                if (
                                    str_raw_value
                                    and str_raw_value.lower()
                                    == 'true'
                                )
                                else 0
                            )
                            continue

                        val_value = (
                            html.unescape(str_raw_value)
                            if str_raw_value
                            else None
                        )
                        
                        if (
                            "rules" in dict_field and val_value is not None
                        ):
                            for dict_rule in dict_field["rules"]:
                                str_action = dict_rule.get("action")
                                if str_action == "replace":
                                    val_value = val_value.replace(
                                        dict_rule.get("target", ""),
                                        dict_rule.get("with", ""),
                                    )
                                elif str_action == "strip":
                                    val_value = val_value.strip()
                                elif str_action == "contains":
                                    val_value = (
                                        dict_rule.get("on_true", 1)
                                        if dict_rule.get("target")
                                        in val_value
                                        else dict_rule.get("on_false", 0)
                                    )
                                    break
                                elif str_action == "map_flags":
                                    val_result = dict_rule.get("default", 0)
                                    for dict_map_flag in dict_rule.get(
                                        "mappings", []
                                    ):
                                        if (
                                            dict_map_flag.get("target")
                                            in val_value
                                        ):
                                            val_result = dict_map_flag.get("value")
                                            break
                                    val_value = val_result
                                    break
                                elif str_action == "format_YYYYMMDD":
                                    if len(val_value) >= 8:
                                        val_value = (
                                            f"{val_value[0:4]}-"
                                            f"{val_value[4:6]}-"
                                            f"{val_value[6:8]}"
                                        )
                                elif str_action == "count_multidisc":
                                    if val_value.lower().endswith('.m3u'):
                                        str_base_name = os.path.splitext(val_value)[0]
                                        str_md_path = os.path.join(
                                            VAR_ROMS_DIR, str_system_folder, 
                                            VAR_HIDDEN_MULTI, str_base_name,
                                        )
                                        if (
                                            os.path.exists(str_md_path)
                                            and os.path.isdir(str_md_path)
                                        ):
                                            val_value = len([
                                                f
                                                for f in os.listdir(
                                                    str_md_path
                                                )
                                                if os.path.isfile(
                                                    os.path.join(
                                                        str_md_path,
                                                        f,
                                                    )
                                                )
                                            ])
                                        else:
                                            val_value = 1
                                    else:
                                        val_value = 1
                                    break

                        dict_game_parsed[str_column] = (
                            val_value if val_value is not None else ""
                        )

                    dict_xml_data[str_xml_filename] = dict_game_parsed

                # --- 3. DELTA CALCULATION AND QUERIES ---
                set_db_files = set(dict_db_data.keys())
                set_xml_files = set(dict_xml_data.keys())

                set_files_to_delete = set_db_files - set_xml_files
                set_files_to_insert = set_xml_files - set_db_files
                set_files_in_common = set_db_files & set_xml_files

                int_system_modifications = 0

                for str_f_del in set_files_to_delete:
                    cursor_db.execute(
                        "DELETE FROM roms WHERE sistema = ? AND filename = ?", 
                        (str_system_folder, str_f_del),
                    )
                    int_total_deleted += 1
                    int_system_modifications += 1

                for str_f_ins in set_files_to_insert:
                    dict_data_ins = dict_xml_data[str_f_ins]
                    list_cols = [
                        'sistema', 'filename', 'last_scanned'
                    ] + list(dict_data_ins.keys())
                    list_vals = [
                        str_system_folder, str_f_ins, str_now
                    ] + list(dict_data_ins.values())
                    
                    str_placeholders = ', '.join(['?'] * len(list_cols))
                    str_query_ins = (
                        f"INSERT INTO roms ({', '.join(list_cols)}) "
                        f"VALUES ({str_placeholders})"
                    )
                    cursor_db.execute(str_query_ins, list_vals)
                    int_total_inserted += 1
                    int_system_modifications += 1

                for str_f_com in set_files_in_common:
                    dict_dati_db = dict_db_data[str_f_com]
                    dict_dati_xml = dict_xml_data[str_f_com]
                    dict_db_clean = {
                        k: (v if v is not None else "")
                        for k, v in dict_dati_db.items()
                    }
                    
                    if dict_db_clean != dict_dati_xml:
                        str_set_clause = ', '.join(
                            [f"{k} = ?" for k in dict_dati_xml.keys()]
                        )
                        list_vals_upd = (
                            list(dict_dati_xml.values())
                            + [str_now, str_system_folder, str_f_com]
                        )
                        str_query_upd = (
                            "UPDATE roms SET "
                            f"{str_set_clause}, last_scanned = ? "
                            "WHERE sistema = ? AND filename = ?"
                        )
                        cursor_db.execute(str_query_upd, list_vals_upd)
                        int_total_updated += 1
                        int_system_modifications += 1

                if int_system_modifications > 0:
                    int_systems_affected += 1

        conn_db.commit()
        conn_db.close()

        print(f"[{GREEN}OK{RESET}] {trf('dbmanager.success_scan')}\n")
        print(
            f" {trf('dbmanager.stat_systems'):<35} : "
            f"{CYAN}{int_systems_affected}{RESET}"
        )
        print(
            f" {trf('dbmanager.stat_inserted'):<35} : "
            f"{GREEN}{int_total_inserted}{RESET}"
        )
        print(
            f" {trf('dbmanager.stat_updated'):<35} : "
            f"{YELLOW}{int_total_updated}{RESET}"
        )
        print(
            f" {trf('dbmanager.stat_deleted'):<35} : "
            f"{RED}{int_total_deleted}{RESET}\n"
        )

    except sqlite3.Error as exc_sqlite:
        str_sq_err = trf('dbmanager.error_sqlite', error=exc_sqlite)
        print(f"[{RED}ERRORE{RESET}] {str_sq_err}")
    except Exception as exc_unexpected:
        str_un_err = trf('dbmanager.error_unexpected', error=exc_unexpected)
        print(f"[{RED}ERRORE{RESET}] {str_un_err}")

    input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")


def oper_full_db_population():
    """
    Full Rom Update:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Just a JEDI Mind Trick, this empties the vault database, then calls 
    oper_incr_db_population(22) to force a full repopulation pretending
    the Δ is the whole ROMs' collection.
    (...these aren't the roms you are looking for...)
    ---
    Parameter:  None
    
    Returns:    Nothing
    """
    util_clean_screen(22)
    print(f"{YELLOW}{trf('dbmanager.deep_clean_init')}{RESET}")

    if not os.path.exists(DB_FILE):
        str_db_msg = trf('dbmanager.db_not_found')
        print(f"\n{RED}{str_db_msg}{RESET}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    try:
        conn_db = sqlite3.connect(DB_FILE)
        cursor_db = conn_db.cursor()

        cursor_db.execute("DELETE FROM roms")
        try:
            cursor_db.execute("DELETE FROM sqlite_sequence WHERE name='roms'")
        except sqlite3.Error:
            pass
            
        conn_db.commit()
        conn_db.close()

    except sqlite3.Error as exc_sqlite:
        str_sq_err = trf('dbmanager.error_sqlite', error=exc_sqlite)
        print(f"\n[{RED}ERRORE{RESET}] {str_sq_err}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return
    except Exception as exc_unexpected:
        str_un_err = trf('dbmanager.error_unexpected', error=exc_unexpected)
        print(f"\n[{RED}ERRORE{RESET}] {str_un_err}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    oper_incr_db_population(menuitem=22)


def oper_google_sheets_sync():
    """
    Google Sheets Synchronization Engine:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Reads the populated SQLite database and synchronizes ROM data to the
    configured Google Sheets document. Features a feature-flag check (wall message
    if disabled), .sec credentials validation (existence & JSON syntax check),
    and robust error handling.
    ---
    Parameters:   None
    Returns:      None
    """
    util_clean_screen(3)

    # 1. Check if the feature flag is enabled in the configuration
    # Accepts boolean True or string 'true' (case-insensitive)
    bool_is_enabled = str(VAR_GSHEET_EXPORT).strip().lower() in (
        "true", "1", "yes", "on"
    )
    if not bool_is_enabled:
        print(f"{YELLOW}{trf('googleexport.feature_disabled_title')}{RESET}\n")
        print(f"{CYAN}{trf('googleexport.feature_disabled_msg')}{RESET}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    print(f"{YELLOW}{trf('googleexport.start_sync')}{RESET}\n")

    # 2. Check existence of the credentials file
    str_sec_file = "romvault.sec"
    if not os.path.exists(str_sec_file):
        str_err_msg = trf('googleexport.sec_not_found')
        print(f"{str_err_msg}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    # 3. Check JSON syntax validity of the credentials file
    try:
        with open(str_sec_file, 'r', encoding='utf-8') as f_sec:
            json.load(f_sec)
    except json.JSONDecodeError:
        str_err_json = trf('googleexport.sec_invalid_json')
        print(f"{str_err_json}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    # 4. Check existence of the local SQLite database
    if not os.path.exists(DB_FILE):
        str_err_db = trf('googleexport.db_not_found', db_file=DB_FILE)
        print(f"{RED}{str_err_db}{RESET}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    try:
        str_auth_msg = trf('googleexport.auth_progress')
        print(f"[{YELLOW}INFO{RESET}] {str_auth_msg}")
        obj_google_client = gspread.service_account(filename=str_sec_file)

        str_conn_msg = trf('googleexport.connect_sheet', sheet_name=VAR_GSHEET_NAME)
        print(f"[{YELLOW}INFO{RESET}] {str_conn_msg}")
        obj_spreadsheet = obj_google_client.open(VAR_GSHEET_NAME)
        obj_worksheet = obj_spreadsheet.sheet1

        str_extract_msg = trf('googleexport.extract_data')
        print(f"[{YELLOW}INFO{RESET}] {str_extract_msg}")
        conn_db = sqlite3.connect(DB_FILE)
        cursor_db = conn_db.cursor()

        # Select columns, excluding internal ID
        cursor_db.execute('''
            SELECT sistema, name, hasachi, genre, nummedia, hidden, broken, 
                   completed, releasedate, publisher, filename, last_scanned
            FROM roms
            ORDER BY sistema, name
        ''')
        list_db_rows = cursor_db.fetchall()
        conn_db.close()

        # Prepare localized header row for Google Sheets using string trf keys
        list_headers = [
            trf('googleexport.col_system'),
            trf('googleexport.col_title'),
            trf('googleexport.col_trophies'),
            trf('googleexport.col_genre'),
            trf('googleexport.col_media'),
            trf('googleexport.col_hidden'),
            trf('googleexport.col_broken'),
            trf('googleexport.col_completed'),
            trf('googleexport.col_release'),
            trf('googleexport.col_publisher'),
            trf('googleexport.col_file'),
            trf('googleexport.col_last_scanned')
        ]

        # Build complete matrix (Headers + Data rows)
        dict_hasachi_map = {0: "-", 1: "Y", 2: "W"}
        list_matrix = [list_headers]
        for tuple_row in list_db_rows:
            list_row_data = list(tuple_row)
            # list_row_data[2] corresponds to 'hasachi' based on SELECT order
            list_row_data[2] = dict_hasachi_map.get(list_row_data[2], "-") 
            list_matrix.append(list_row_data)
        
        str_transfer_msg = trf(
            'googleexport.transfer_progress',
            total_rows=len(list_db_rows),
        )
        print(f"[{YELLOW}INFO{RESET}] {str_transfer_msg}")

        # Clear old sheet contents and update with new data in a single batch API call
        obj_worksheet.clear()
        obj_worksheet.update(values=list_matrix, range_name='A1')

        str_success_msg = trf('googleexport.sync_success')
        print(f"{GREEN}[OK] {str_success_msg}{RESET}")

    except gspread.exceptions.SpreadsheetNotFound:
        str_sheet_err = trf('googleexport.sheet_not_found', 
                            sheet_name=VAR_GSHEET_NAME)
        print(f"{RED}[ERRORE]{RESET} {str_sheet_err}")
    except Exception as exc_sync:
        str_unexp_err = trf('googleexport.unexpected_error', error=exc_sync)
        print(f"{RED}[ERRORE]{RESET} {str_unexp_err}")

    input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")


def menu_rom_manager():
    """
    Menu ROMs Manager:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Submenu: Advanced ROMs Management
    Draw the submenu.
    ---
    Parameter:  None
    
    Returns:    Nothing
    """
    while True:
        util_clean_screen(4)
        print(f"{GREEN} 1 {RESET}- {trf('menu.item_41')}")
        print(f"{GREEN} 2 {RESET}- {trf('menu.item_42')}")
        print(f"{GREEN} 3 {RESET}- {trf('menu.item_43')}")
        print(f"{RED} X {RESET}- {trf('menu.item_back')}")
        print()

        # input case-insensitive (x o X)
        input_choice = input(f"{CYAN}{trf(
            'generic.prompt_select')}{RESET}").strip().upper()
        print("\n")

        match input_choice:
            case '1':
                oper_crosscheck_fs_xml()
            case '2':
                oper_deepaudit_rom_archives()
            case '3':
                oper_triage_roms()
            case 'X':
                # Leave this submenu and go back to the main.
                break
            case _:
                print(f"{RED}{trf('generic.invalid_command')}{RESET}")
                input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")


def oper_crosscheck_fs_xml():
    """
    Cross-check Filesystem and XML Engine:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Scans the filesystem, then cross-references data with the various
    gamelist.xml files to highlight specific anomalies, performing
    punctual numerical counts and record analysis against the SQLite database.
    ---
    Parameters: None
    
    Returns:    None
    """
    util_clean_screen(41)

    # STRICT CONFIGURATION CHECK
    if 'VAR_REPORT_DIR' not in globals() or not VAR_REPORT_DIR:
        util_error_display(41, "E", (1,), "bck")
        return None
    os.makedirs(VAR_REPORT_DIR, exist_ok=True)

    if not os.path.exists(VAR_ROMS_DIR):
        util_error_display(41, "E", (2,), "bck")
        return

    # Animated spinner characters
    lst_spinner = ['\\', '|', '/', '-']
    int_spin_idx = 0

    # Unified global matrix for all systems and vault ROMs
    lst_global_rom_matrix = []

    # 1. Structured loading of records from the SQLite Database
    dict_db_files_per_system = {}
    if os.path.exists(DB_FILE):
        try:
            conn_db = sqlite3.connect(DB_FILE)
            cursor_db = conn_db.cursor()
            cursor_db.execute("SELECT sistema, filename FROM roms")
            for str_sys_name, str_filename in cursor_db.fetchall():
                str_sys_low = str_sys_name.lower()
                if str_sys_low not in dict_db_files_per_system:
                    dict_db_files_per_system[str_sys_low] = set()
                dict_db_files_per_system[str_sys_low].add(str_filename)
            conn_db.close()
        except Exception:
            pass

    # Tracking set for systems encountered on the filesystem
    set_processed_systems = set()

    # 2. Scanning and unified population from Filesystem
    #    and XML Gamelists
    if os.path.exists(VAR_ROMS_DIR):
        for str_system_folder in os.listdir(VAR_ROMS_DIR):
            str_system_path = os.path.join(VAR_ROMS_DIR, str_system_folder)

            if (
                not os.path.isdir(str_system_path)
                or str_system_folder.startswith('.')
                or str_system_folder.lower() == 'cleanup'
            ):
                continue

            # SPINNER Refresh -----------
            str_char = lst_spinner[int_spin_idx % len(lst_spinner)]
            sys.stdout.write(f"\r\033[K{trf('crosscheck.waitin')} [{str_char}]")
            sys.stdout.flush()
            int_spin_idx += 1
            # ---------------------------
            
            str_sys_low = str_system_folder.lower()
            set_processed_systems.add(str_sys_low)

            # Collection of actual files on the filesystem
            set_fs_files = set()
            match str_sys_low:
                case "scummvm":
                    try:
                        lst_subfolders = [
                            d for d in os.listdir(str_system_path)
                            if os.path.isdir(os.path.join(str_system_path, d))
                        ]
                        for str_sub in lst_subfolders:
                            set_fs_files.add(str_sub)
                    except Exception:
                        pass
                case _:
                    for str_root, lst_dirs, lst_files in os.walk(str_system_path):
                        if VAR_HIDDEN_MULTI in str_root:
                            continue
                        for str_file in lst_files:
                            str_file_low = str_file.lower()
                            # Ignore system files and support files (.sbi)
                            if (
                                str_file_low == 'systeminfo.txt'
                                or str_file_low.endswith('.sbi')
                            ):
                                continue
                            set_fs_files.add(str_file)

            # Collection of data from XML
            int_listed, int_hidden, set_xml_files = util_xml_scan(
                str_system_folder
            )
            int_effective_listed = int_listed - int_hidden            
            
            # Retrieval of files indexed in the Database for this system
            set_db_files = dict_db_files_per_system.get(str_sys_low, set())

            # Union of all unique filenames coming from any source
            set_all_filenames = (
                set_fs_files.union(set_xml_files).union(set_db_files)
            )

            # Construction of unified records for the global matrix
            for str_filename in set_all_filenames:
                bool_on_fs = str_filename in set_fs_files
                bool_in_db = str_filename in set_db_files
                bool_in_xml = str_filename in set_xml_files
                
                # Registration of the normalized record in global matrix
                lst_global_rom_matrix.append({
                    "str_system": str_system_folder,
                    "str_filename": str_filename,
                    "bool_on_fs": bool_on_fs,
                    "bool_in_db": bool_in_db,
                    "bool_in_xml": bool_in_xml,
                    "int_xml_total": int_effective_listed,
                    "int_hidden_total": int_hidden
                })

    # 3. Cross-check on orphan Gamelists paths
    #    (systems present only in XML)
    if os.path.exists(VAR_GAMELIST_DIR):
        for str_system_folder in os.listdir(VAR_GAMELIST_DIR):
            str_system_path = os.path.join(VAR_GAMELIST_DIR, str_system_folder)

            if (
                not os.path.isdir(str_system_path)
                or str_system_folder.startswith('.')
                or str_system_folder.lower() == 'cleanup'
            ):
                continue

            # SPINNER Refresh -----------
            str_char = lst_spinner[int_spin_idx % len(lst_spinner)]
            sys.stdout.write(f"\r\033[K{trf('crosscheck.waitin')} [{str_char}]")
            sys.stdout.flush()
            int_spin_idx += 1
            # ---------------------------

            str_sys_low = str_system_folder.lower()
            if str_sys_low not in set_processed_systems:
                int_listed, int_hidden, set_xml_files = (
                    util_xml_scan(str_system_folder)
                )
                set_db_files = dict_db_files_per_system.get(str_sys_low, set())
                
                set_all_filenames = set_xml_files.union(set_db_files)
                for str_filename in set_all_filenames:
                    lst_global_rom_matrix.append({
                        "str_system": str_system_folder,
                        "str_filename": str_filename,
                        "bool_on_fs": False,
                        "bool_in_db": str_filename in set_db_files,
                        "bool_in_xml": str_filename in set_xml_files
                    })

    # 4. Global dynamic width calculation for report column sizing
    int_max_filename_length = max(
        (len(dict_row["str_filename"]) for dict_row in lst_global_rom_matrix),
        default=20
    )
    util_clean_screen(41)

    # Systems matrix generation aggregating data from global matrix
    dict_systems_summary = {}

    for dict_row in lst_global_rom_matrix:
        str_system_name = dict_row["str_system"]
        if str_system_name not in dict_systems_summary:
            dict_systems_summary[str_system_name] = {
                "int_fs_count": 0,
                "int_xml_count": dict_row.get("int_xml_total", 0),
                "int_hidden_count": dict_row.get("int_hidden_total", 0),
                "int_db_count": 0,
                "bool_has_discrepancy": False
            }
        
        # Updating counters based on presence flags in global matrix
        if dict_row["bool_on_fs"]:
            dict_systems_summary[str_system_name]["int_fs_count"] += 1
        if dict_row["bool_in_db"]:
            dict_systems_summary[str_system_name]["int_db_count"] += 1
            
        # Detecting discrepancies between sources for the same file
        if not (
            dict_row["bool_on_fs"]
            == dict_row["bool_in_db"]
            == dict_row["bool_in_xml"]
        ):
            dict_systems_summary[str_system_name]["bool_has_discrepancy"] = True

    # Conversion into structured list for video dashboard
    lst_systems_summary = []
    for str_system_name, dict_data in dict_systems_summary.items():
        str_status = "KO" if dict_data["bool_has_discrepancy"] else "OK"
        
        lst_systems_summary.append([
            str_system_name, 
            dict_data["int_fs_count"], 
            dict_data["int_xml_count"], 
            dict_data["int_hidden_count"], 
            dict_data["int_db_count"], 
            str_status
        ])

    # Sorting: KOs first, then OKs (secondary alphabetical sort on name)
    lst_systems_summary.sort(key=lambda x: (0 if x[5] == "KO" else 1, x[0]))

    # Dashboard screen display (fixed 8-line viewport)
    int_max_content_rows = 7
    int_printed_rows = 0

    for lst_sys_row in lst_systems_summary[:int_max_content_rows]:
        str_status_color = GREEN if lst_sys_row[5] == "OK" else RED
        print(
            f"{trf('crosscheck.small_tbl_1')}: {lst_sys_row[0]:<15} | "
            f"{trf('crosscheck.small_tbl_2')}: {lst_sys_row[1]:>4} | "
            f"{trf('crosscheck.small_tbl_3')}: {lst_sys_row[2]:>4} + "
            f"{lst_sys_row[3]:>2} | "
            f"{trf('crosscheck.small_tbl_4')}: {lst_sys_row[4]:>4} | "
            f"{trf('crosscheck.small_tbl_5')}: {str_status_color}"
            f"{lst_sys_row[5]}{RESET}"
        )
        int_printed_rows += 1

    if len(lst_systems_summary) > int_max_content_rows:
        str_more_details = trf('crosscheck.more_details')
        print(f"{YELLOW}{str_more_details}{RESET}")
        int_printed_rows += 1

    while int_printed_rows < 8:
        print()
        int_printed_rows += 1

    # --- REPORT FILE MANAGEMENT AND EXPORT (ALWAYS ACTIVE) ---
    str_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    str_report_path = os.path.join(
        VAR_REPORT_DIR,
        f"crosscheck_report_{str_timestamp}.log"
    )
    
    try:
        with open(str_report_path, "w", encoding="utf-8") as f_rep:
            f_rep.write(f"{trf('crosscheck.rep_title')}\n")
            f_rep.write("=" * 80 + "\n\n")
            
            # Section 1: Global summary table of ALL systems
            f_rep.write(f"{trf('crosscheck.rep_global_stat')}\n")
            
            str_hdr_sys = trf('crosscheck.rep_header_sys')
            str_hdr_status = trf('crosscheck.rep_header_status')
            f_rep.write(
                f"{str_hdr_sys:<18} | {'FS':>6} | {'XML+Hid':>9} | "
                f"{'DB':>6} | {str_hdr_status:<5}\n"
            )
            f_rep.write("-" * 55 + "\n")
            
            for lst_sys_row in lst_systems_summary:
                str_sys_name = lst_sys_row[0]
                int_fs_count = lst_sys_row[1]
                int_xml_count = lst_sys_row[2]
                int_hidden_count = lst_sys_row[3]
                int_db_count = lst_sys_row[4]
                str_status = lst_sys_row[5]
                
                str_ko_marker = " <---" if str_status == "KO" else ""
                
                f_rep.write(
                    f"{str_sys_name:<18} | "
                    f"{int_fs_count:>6} | "
                    f"{int_xml_count:>4} + {int_hidden_count:<2} | "
                    f"{int_db_count:>6} | "
                    f"{str_status:<5}{str_ko_marker}\n"
                )
            
            f_rep.write("\n" + "=" * 80 + "\n\n")
            
            # Section 2: Analytical table of anomalies
            lst_anomalous_rows = [
                dict_row for dict_row in lst_global_rom_matrix
                if not (
                    dict_row["bool_on_fs"]
                    == dict_row["bool_in_db"]
                    == dict_row["bool_in_xml"]
                )
            ]
            
            lst_anomalous_rows.sort(
                key=lambda x: (x["str_system"], x["str_filename"])
            )
            
            if lst_anomalous_rows:
                str_anomalies_title = trf(
                    'crosscheck.rep_anomalies_title',
                    count=len(lst_anomalous_rows)
                )
                f_rep.write(f"{str_anomalies_title}\n")
                
                # Adapting table lenght for the report to the anomalies matrix
                # and not to the whole game matrix as earlier.
                int_local_max_len = max(
                    (len(dict_row["str_filename"]) for dict_row in lst_anomalous_rows),
                    default=15
                )
                int_col_width = max(15, int_local_max_len + 2)
                
                str_header_format = (
                    f"{{:<{int_col_width}}} | {{:^6}} | {{:^6}} | {{:^6}}\n"
                )
                str_hdr_rom = trf('crosscheck.rep_header_rom')
                f_rep.write(
                    str_header_format.format(str_hdr_rom, "FS", "DB", "XML")
                )
                f_rep.write("-" * (int_col_width + 26) + "\n")
                
                str_current_system = ""
                for dict_row in lst_anomalous_rows:
                    if dict_row["str_system"] != str_current_system:
                        str_current_system = dict_row["str_system"]
                        str_sys_group = trf(
                            'crosscheck.rep_system_group',
                            system=str_current_system
                        )
                        f_rep.write(f"{str_sys_group}\n")
                    
                    str_fs_flag = "X" if dict_row["bool_on_fs"] else "-"
                    str_db_flag = "X" if dict_row["bool_in_db"] else "-"
                    str_xml_flag = "X" if dict_row["bool_in_xml"] else "-"
                    
                    str_row_format = (
                        f"{{:<{int_col_width}}} | {{:^6}} | {{:^6}} | {{:^6}}\n"
                    )
                    f_rep.write(
                        str_row_format.format(
                            dict_row["str_filename"],
                            str_fs_flag,
                            str_db_flag,
                            str_xml_flag
                        )
                    )
            else:
                f_rep.write(f"{trf('crosscheck.rep_no_anomalies')}\n")
                
    except Exception as exc_err:
        pass    
    
    # --- FIXED FOOTER ---
    print()
    print(f"{CYAN}{'-' * 80}{RESET}")
    
    int_total_anomalies = len([
        dict_row for dict_row in lst_global_rom_matrix
        if not (
            dict_row["bool_on_fs"]
            == dict_row["bool_in_db"]
            == dict_row["bool_in_xml"]
        )
    ])
    
    str_anomaly_color = RED if int_total_anomalies > 0 else GREEN
    str_status_lbl = trf('crosscheck.status_anomalies')
    str_status_cnt = trf(
        'crosscheck.status_anomalies_count',
        count=int_total_anomalies
    )
    
    print(
        f"{str_status_lbl} {str_anomaly_color}{str_status_cnt}{RESET}"
    )
    
    str_saved_report = trf('crosscheck.saved_in_report')
    print(f"{CYAN}{str_saved_report}{RESET}")
    print(f"{str_report_path}")
        
    print()
    input(f"{YELLOW}{trf('generic.press_enter')}{RESET}")
    return None


def oper_deepaudit_rom_archives():
    """
    Deep Audit ROM Archives Engine:
    v.1.1 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Performs a deep audit of compressed archives (.zip and .7z), comparing
    the internal file extension with expected extensions for each system.
    Leverages the 'zipchk' cache flag in the database and filters only
    cartridge-based systems. Handles KeyboardInterrupt gracefully and
    exports anomalies to a specific log file.
    ---
    Parameters: None
    
    Returns:    None
    """

    util_clean_screen(42)
    print(f"{YELLOW}{trf('deepaudit.start_audit')}{RESET}")
    print(f"{CYAN}{trf('deepaudit.info_audit')}{RESET}\n")

    os.makedirs(VAR_REPORT_DIR, exist_ok=True)

    if not os.path.exists(DB_FILE):
        str_err_db = trf('deepaudit.err_db', DB_FILE=DB_FILE)
        print(f"{RED}{str_err_db}{RESET}")
        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
        return

    int_total_updated = 0
    lst_anomalies = []
    lst_debug_lines = []
    conn_db = None

    try:
        conn_db = sqlite3.connect(DB_FILE)
        cur_db = conn_db.cursor()

        # Generate the list of valid systems from the global dictionary
        lst_valid_systems = list(DICT_EXPECTED_EXTENSIONS.keys())
        
        # Create dynamic placeholders (?, ?, ?) for the IN (...) query
        str_placeholders = ', '.join(['?'] * len(lst_valid_systems))
        
        # Targeted query: select archives (.zip or .7z) of cartridge systems
        # that have not yet been validated
        str_query = f"""
            SELECT id, sistema, filename 
            FROM roms 
            WHERE (filename LIKE '%.zip' OR filename LIKE '%.7z')
              AND (zipchk IS NULL OR zipchk != 1)
              AND LOWER(sistema) IN ({str_placeholders})
        """
        cur_db.execute(str_query, lst_valid_systems)
        lst_records = cur_db.fetchall()

        int_total_to_verify = len(lst_records)

        if int_total_to_verify == 0:
            str_all_valid = trf('deepaudit.all_validated')
            print(f"[{GREEN}OK{RESET}] {str_all_valid}")
            conn_db.close()
            input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
            return

        str_found = trf(
            'deepaudit.found_archives', count=int_total_to_verify
        )
        print(f"[{YELLOW}INFO{RESET}] {str_found}")

        # Characters for the animated spinner
        lst_spinner = ['\\', '|', '/', '-']
        int_spin_idx = 0

        try:
            for int_row_id, str_system, str_filename in lst_records:
                # Update the spinner
                str_char = lst_spinner[int_spin_idx % len(lst_spinner)]
                str_spin_msg = trf('deepaudit.spinner_analysis')
                sys.stdout.write(
                    f"\r\033[K{CYAN}{str_spin_msg} [{str_char}]{RESET}"
                )
                sys.stdout.flush()
                int_spin_idx += 1

                str_archive_path = os.path.join(
                    VAR_ROMS_DIR, str_system, str_filename
                )

                if not os.path.exists(str_archive_path):
                    str_prob_fs = trf('deepaudit.err_fs_not_found')
                    lst_anomalies.append({
                        "str_system": str_system,
                        "str_file": str_filename,
                        "str_problem": str_prob_fs
                    })

                # --- CALL TO THE CENTRALIZED SUPER-FUNCTION ---
                dict_res = util_analyze_archive(str_archive_path, str_system)

                if dict_res["file_ok"]:
                    # Extract calculated and normalized data from result dict
                    str_crc32 = dict_res["crc32"]
                    str_md5 = dict_res["md5"]
                    str_internal_name = dict_res["internal_filename"]

                    # Database Update
                    str_upd = (
                        "UPDATE roms SET zipchk = 1, crc32 = ?, md5 = ?, "
                        "internal_filename = ? WHERE id = ?"
                    )
                    cur_db.execute(
                        str_upd,
                        (str_crc32, str_md5, str_internal_name, int_row_id)
                    )

                    int_total_updated += 1
                    
                    # Batch commit every 200 records for optimal performance
                    if int_total_updated % 200 == 0:
                        conn_db.commit()
                else:
                    str_prob_arch = dict_res["motivo"]
                    lst_anomalies.append({
                        "str_system": str_system,
                        "str_file": str_filename,
                        "str_problem": str_prob_arch
                    })

        except KeyboardInterrupt:
            # Handle Ctrl+C gracefully during the loop
            str_interrupt = trf(
                'deepaudit.interrupt_msg',
                count=int_total_updated
            )
            print(f"\n\n{YELLOW}{str_interrupt}{RESET}")
            
        finally:
            # Clean the spinner line completely
            sys.stdout.write("\r\033[K")
            sys.stdout.flush()

            if conn_db:
                conn_db.commit()
                conn_db.close()

        # Print statistical results
        print(f"[{GREEN}OK{RESET}] {trf('deepaudit.audit_completed')}")
        
        str_stat_upd = trf('deepaudit.stat_updated')
        print(
            f" - {str_stat_upd:<35} : "
            f"{GREEN}{int_total_updated}{RESET}"
        )
        
        str_stat_anom = trf('deepaudit.stat_anomalies')
        str_anom_color = RED if lst_anomalies else GREEN
        print(
            f" - {str_stat_anom:<35} : "
            f"{str_anom_color}{len(lst_anomalies)}{RESET}\n"
        )

        # --- REPORT FILE CREATION LOGIC ---
        # Generate the report only if there are anomalies
        if lst_anomalies:
            str_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            str_rep_path = os.path.join(
                VAR_REPORT_DIR, f"deepaudit_report_{str_timestamp}.log"
            )
            
            try:
                with open(str_rep_path, "w", encoding="utf-8") as f_rep:
                    f_rep.write(f"{trf('deepaudit.rep_title')}\n")
                    f_rep.write("=" * 80 + "\n\n")
                    
                    if lst_anomalies:
                        str_anom_title = trf(
                            'deepaudit.rep_anomalies_title',
                            count=len(lst_anomalies)
                        )
                        f_rep.write(f"{str_anom_title}\n")
                        f_rep.write("-" * 80 + "\n")
                        
                        for dict_anom in lst_anomalies:
                            str_row = trf(
                                'deepaudit.rep_anomaly_row',
                                system=dict_anom['str_system'],
                                file=dict_anom['str_file']
                            )
                            str_prob = dict_anom['str_problem']
                            f_rep.write(f"{str_row}{str_prob}\n")

                str_saved_rep = trf('deepaudit.saved_in_report')
                print(f"{CYAN}{str_saved_rep}{RESET}")
                print(f"{str_rep_path}")
                
            except Exception as exc_rep:
                pass
        
    except sqlite3.Error as exc_sqlite:
        str_err_sql = trf('deepaudit.err_sqlite')
        print(f"\n{RED}{str_err_sql}{RESET} {exc_sqlite}")
    except Exception as exc_unexpected:
        str_err_unexp = trf('deepaudit.err_unexpected')
        print(f"\n{RED}{str_err_unexp}{RESET} {exc_unexpected}")
    
    print()
    input(f"{YELLOW}{trf('generic.press_enter')}{RESET}")


def oper_triage_roms():
    """
    Triage ROMs Management Engine:
    v.1.3 Completion status 100%
    Multilanguage support 100%
    TO DO: None

    Starts the Triage process for new ROMs by applying title
    normalization, family grouping, and heuristic scoring comparison.
    Natively supports .zip and .7z archives.
    ---
    Parameters: None
    
    Returns:    None
    """
    if not os.path.exists(DB_FILE):
        util_error_display(43, "E", (1, 2, 3), "fwd")
        return None

    # STRICT CONFIGURATION CHECK FOR REPORT DIRECTORY
    if 'VAR_REPORT_DIR' not in globals() or not VAR_REPORT_DIR:
        util_error_display(43, "E", (1,), "bck")
        return None
    os.makedirs(VAR_REPORT_DIR, exist_ok=True)

    try:
        conn_db = sqlite3.connect(DB_FILE)
        cur_db = conn_db.cursor()
        str_target_system = util_cartridge_system_choice(cur_db)
        
        if not str_target_system:
            conn_db.close()
            return

        util_clean_screen(43)
        
        str_source_dir = os.path.join(
            VAR_ROMS_DIR, str_target_system, ""
        )
        str_suggested_path = os.path.join(VAR_INCOMING_DIR, "")
        str_current_value = str_suggested_path
        str_error_message = ""
        
        while True:
            util_clean_screen(43)
            print(
                f"[{GREEN}OK{RESET}] "
                f"{trf('triage.status_sys_selected'):<20} "
                f"{CYAN}{str_target_system}{RESET}"
            )
            print(
                f"[{GREEN}OK{RESET}] "
                f"{trf('triage.status_active_folder'):<20} "
                f"{CYAN}{str_source_dir}{RESET}\n"
            )
            
            if str_error_message:
                print(f"[{RED}ERRORE{RESET}] {str_error_message}")
            else:
                print("")
            
            str_target_dir = util_pre_compiled_input(
                trf('triage.prompt_incoming_path'), str_current_value
            ).strip()
            
            if not str_target_dir:
                print(
                    f"\n[{YELLOW}INFO{RESET}] {trf('triage.op_cancelled')}"
                )
                input(f"\n{YELLOW}{trf('generic.press_back')}{RESET}")
                conn_db.close()
                return
                
            if os.path.isdir(str_target_dir):
                util_clean_screen(43)
                str_target_dir = os.path.join(str_target_dir, "")
                print(
                    f"[{GREEN}OK{RESET}] "
                    f"{trf('triage.status_sys_selected'):<20} "
                    f"{CYAN}{str_target_system}{RESET}"
                )
                print(
                    f"[{GREEN}OK{RESET}] "
                    f"{trf('triage.status_active_folder'):<20} "
                    f"{CYAN}{str_source_dir}{RESET}"
                )
                print(
                    f"[{GREEN}OK{RESET}] "
                    f"{trf('triage.status_incoming_folder'):<20} "
                    f"{CYAN}{str_target_dir}{RESET}\n"
                )
                break
            else:
                str_error_message = trf('triage.err_invalid_folder')
                str_current_value = str_target_dir

        lst_valid_extensions = DICT_EXPECTED_EXTENSIONS.get(
            str_target_system.lower(), []
        )
        if not lst_valid_extensions:
            print(
                f"\n[{YELLOW}WARNING{RESET}] "
                f"{trf('triage.warn_no_extensions', system=str_target_system)}"
            )
            input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
            conn_db.close()
            return

        lst_found_files = [
            f for f in os.listdir(str_target_dir)
            if f.lower().endswith(('.zip', '.7z'))
            and os.path.isfile(os.path.join(str_target_dir, f))
        ]
        
        if not lst_found_files:
            print(
                f"\n[{YELLOW}INFO{RESET}] {trf('triage.info_no_archives')}"
            )
            input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")
            conn_db.close()
            return
        
        # Active DNA mapping in background without redundant prints
        cur_db.execute(
            "SELECT crc32, filename FROM roms WHERE sistema = ?",
            (str_target_system,)
        )
        lst_db_rows = cur_db.fetchall()
        conn_db.close()

        dict_active_crc_to_name = {
            row[0]: row[1] for row in lst_db_rows if row[0]
        }
        dict_active_norm_to_data = {}
        for row in lst_db_rows:
            if row[1]:
                str_norm = util_normalize_filename(row[1])
                dict_active_norm_to_data[str_norm] = {
                    'nome_reale': row[1],
                    'score': util_calc_rom_score(row[1])
                }

        # Dynamic in-place spinner feedback appended to the analysis message
        str_analysis_msg = trf('triage.roms_analysis', count=len(lst_found_files))
        print(f"{CYAN}{str_analysis_msg}{RESET}", end="", flush=True)

        lst_spinner = ['\\', '|', '/', '-']
        int_spin_idx = 0
        
        dict_tier_folders = {
            1: "Tier_1_Nuovi",
            2: "Tier_2_Varianti",
            3: "Tier_3_Conflitti",
            4: "Tier_4_Doppioni",
            5: "Tier_5_Scarti"
        }
        dict_stats = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        lst_log_details = []
        
        dict_incoming_families = {}
        
        for str_archive_file in lst_found_files:
            # Spinner update in-place right after the analysis message
            str_char = lst_spinner[int_spin_idx % len(lst_spinner)]
            sys.stdout.write(f"\r{CYAN}{str_analysis_msg} {str_char}{RESET}")
            sys.stdout.flush()
            int_spin_idx += 1

            str_archive_path = os.path.join(
                str_target_dir, str_archive_file
            )
            
            dict_res = util_analyze_archive(
                str_archive_path, str_target_system
            )

            if not dict_res["file_ok"]:
                str_dest_folder = os.path.join(
                    str_target_dir, dict_tier_folders[5]
                )
                os.makedirs(str_dest_folder, exist_ok=True)
                shutil.move(
                    str_archive_path,
                    os.path.join(str_dest_folder, str_archive_file)
                )
                dict_stats[5] += 1
                lst_log_details.append((
                    5,
                    f"staging:{str_archive_file} -> {dict_res['motivo']}"
                ))
            else:
                str_crc32_hex = dict_res["crc32"]
                str_norm = dict_res["archive_norm_title"]
                
                if str_norm not in dict_incoming_families:
                    dict_incoming_families[str_norm] = []
                
                dict_incoming_families[str_norm].append({
                    'file': str_archive_file,
                    'crc': str_crc32_hex,
                    'score': util_calc_rom_score(str_archive_file)
                })

        for str_norm, lst_incoming_variants in dict_incoming_families.items():
            lst_incoming_variants.sort(
                key=lambda x: x['score'], reverse=True
            )
            str_internal_winner = lst_incoming_variants[0]['file']
            
            for int_index, dict_item in enumerate(lst_incoming_variants):
                str_archive_file = dict_item['file']
                str_crc = dict_item['crc']
                int_score = dict_item['score']
                str_archive_path = os.path.join(
                    str_target_dir, str_archive_file
                )
                int_tier = 0
                str_reason = ""
                
                if str_crc in dict_active_crc_to_name:
                    int_tier = 4
                    str_collection_name = dict_active_crc_to_name[str_crc]
                    str_reason = trf(
                        'triage.reasons.duplicate',
                        file=str_archive_file,
                        system=str_target_system,
                        collection=str_collection_name
                    )
                
                elif int_index > 0:
                    int_tier = 4
                    str_reason = trf(
                        'triage.reasons.lower_score',
                        file=str_archive_file,
                        score=int_score,
                        winner=str_internal_winner
                    )
                
                else:
                    if str_norm in dict_active_norm_to_data:
                        dict_active_data = dict_active_norm_to_data[str_norm]
                        int_tier = 2
                        if int_score > dict_active_data['score']:
                            str_reason = trf(
                                'triage.reasons.upgrade',
                                file=str_archive_file,
                                score=int_score,
                                active_score=dict_active_data['score'],
                                system=str_target_system,
                                real_name=dict_active_data['nome_reale']
                            )
                        else:
                            str_reason = trf(
                                'triage.reasons.equal_or_worse',
                                file=str_archive_file,
                                score=int_score,
                                active_score=dict_active_data['score'],
                                system=str_target_system,
                                real_name=dict_active_data['nome_reale']
                            )
                    else:
                        str_matched_variant_name = None
                        int_best_ratio_pct = 0
                        
                        for str_act_norm, dict_act_data in (
                            dict_active_norm_to_data.items()
                        ):
                            obj_matcher = difflib.SequenceMatcher(
                                None, str_norm, str_act_norm
                            )
                            flt_current_ratio = obj_matcher.ratio()
                            
                            if flt_current_ratio > 0.97:
                                str_matched_variant_name = (
                                    dict_act_data['nome_reale']
                                )
                                int_best_ratio_pct = int(
                                    flt_current_ratio * 100
                                )
                                break
                        
                        if str_matched_variant_name:
                            int_tier = 3
                            str_reason = trf(
                                'triage.reasons.conflict',
                                file=str_archive_file,
                                system=str_target_system,
                                matched_name=str_matched_variant_name,
                                ratio=int_best_ratio_pct
                            )
                        else:
                            int_tier = 1
                            str_reason = trf(
                                'triage.reasons.new_game',
                                file=str_archive_file,
                                score=int_score
                            )

                str_dest_folder = os.path.join(
                    str_target_dir, dict_tier_folders[int_tier]
                )
                os.makedirs(str_dest_folder, exist_ok=True)
                shutil.move(
                    str_archive_path,
                    os.path.join(str_dest_folder, str_archive_file)
                )
                dict_stats[int_tier] += 1
                lst_log_details.append((int_tier, str_reason))

        # Clear spinner and analysis line completely
        sys.stdout.write("\r\033[K")
        sys.stdout.flush()

        # Standardized report generation in report folder
        str_timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        str_report_filename = f"triage_report_{str_timestamp}.log"
        str_report_path = os.path.join(VAR_REPORT_DIR, str_report_filename)

        try:
            with open(str_report_path, 'w', encoding='utf-8') as f_rep:
                f_rep.write(
                    f"{trf('triage.rep_title', system=str_target_system)}\n"
                )
                f_rep.write("=" * 80 + "\n\n")
                
                f_rep.write(
                    f"{trf('triage.rep_tier1', count=dict_stats[1])}\n"
                )
                for int_t_num, str_msg in lst_log_details:
                    if int_t_num == 1:
                        str_part_file = (
                            str_msg.replace("staging:", "")
                            .split(" identificato")[0]
                        )
                        f_rep.write(f"    {str_part_file}\n")
                        
                f_rep.write(
                    f"{trf('triage.rep_tier2', count=dict_stats[2])}\n"
                )
                for int_t_num, str_msg in lst_log_details:
                    if int_t_num == 2:
                        f_rep.write(f"    {str_msg}\n")
                        
                f_rep.write(
                    f"{trf('triage.rep_tier3', count=dict_stats[3])}\n"
                )
                for int_t_num, str_msg in lst_log_details:
                    if int_t_num == 3:
                        f_rep.write(f"    {str_msg}\n")
                        
                f_rep.write(
                    f"{trf('triage.rep_tier4', count=dict_stats[4])}\n"
                )
                for int_t_num, str_msg in lst_log_details:
                    if int_t_num == 4:
                        f_rep.write(f"    {str_msg}\n")
                        
                f_rep.write(
                    f"{trf('triage.rep_tier5', count=dict_stats[5])}\n"
                )
                for int_t_num, str_msg in lst_log_details:
                    if int_t_num == 5:
                        f_rep.write(f"    {str_msg}\n")
                        
                f_rep.write("-" * 40 + "\n")
                f_rep.write(f"{trf('triage.rep_footer1')}\n")
                f_rep.write(f"{str_target_dir}\n")
        except Exception as exc_rep:
            print(f"\n{trf('triage.log_error')}{exc_rep}.")

        # Final screen clear to keep dashboard strictly within 24 rows with balanced spacing
        util_clean_screen(43)
        print(
            f"[{GREEN}OK{RESET}] "
            f"{trf('triage.status_sys_selected'):<20} "
            f"{CYAN}{str_target_system}{RESET}"
        )
        print(
            f"[{GREEN}OK{RESET}] "
            f"{trf('triage.status_active_folder'):<20} "
            f"{CYAN}{str_source_dir}{RESET}"
        )
        print(
            f"[{GREEN}OK{RESET}] "
            f"{trf('triage.status_incoming_folder'):<20} "
            f"{CYAN}{str_target_dir}{RESET}\n"
        )

        print(f"{GREEN}{trf('triage.rep_tier1', count=dict_stats[1])}{RESET}")
        print(f"{CYAN}{trf('triage.rep_tier2', count=dict_stats[2])}{RESET}")
        print(f"{YELLOW}{trf('triage.rep_tier3', count=dict_stats[3])}{RESET}")
        print(f"{RED}{trf('triage.rep_tier4', count=dict_stats[4])}{RESET}")
        print(f"{MAGENTA}{trf('triage.rep_tier5', count=dict_stats[5])}{RESET}\n")
        print(
            f"[{GREEN}OK{RESET}] {trf('triage.res_saved_in')}\n"
            f"{CYAN}{str_report_path}{RESET}"
        )

        input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")

    except sqlite3.Error as exc_sqlite:
        util_clean_screen(43)
        print(f"\n{RED}ERRORE SQLite:{RESET} {exc_sqlite}")
        input(f"\n{YELLOW}{trf('generic.press_back')}{RESET}")
        

def main():
    """
    Main menu:
    v.1.0 Completion status 100%
    Multilanguage support 100%
    TO DO: None
    """
    while True:
        util_clean_screen()
        print(f"{GREEN} 1 {RESET}- {trf('menu.item_1')}")
        print(f"{GREEN} 2 {RESET}- {trf('menu.item_2')}")
        print(f"{GREEN} 3 {RESET}- {trf('menu.item_3')}")
        print(f"{GREEN} 4 {RESET}- {trf('menu.item_4')}")
        print(f"{RED} X {RESET}- {trf('menu.item_exit')}")
        print()

        # input case-insensitive (x o X)
        input_choice = input(f"{CYAN}{trf(
            'generic.prompt_select')}{RESET}").strip().upper()
        print()

        match input_choice:
            case '1':
                oper_database_check()
            case '2':
                menu_db_manager()
            case '3':
                oper_google_sheets_sync()
            case '4':
                menu_rom_manager() # Calling submenu loop.
            case 'X':
                # Close the program with error code 0
                print(f"{RED}{trf('generic.closing')}{RESET}")
                sys.exit(0)
            case _:
                print(f"{RED}{trf('generic.invalid_command')}{RESET}")
                input(f"\n{YELLOW}{trf('generic.press_enter')}{RESET}")


if __name__ == "__main__":
    main()
