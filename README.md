<div align="center">

<p align="center">
  <img width="1062" height="116" alt="romvault logo" src="https://github.com/user-attachments/assets/b3239c70-2244-4aaa-86b0-1ce9e45fbfba" />
</p>

**A modular command-line tool for managing, organizing, and tracking ROM collections.**

[![GPL-3.0 License](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![GitHub Workflow Status](https://img.shields.io/badge/status-active-success.svg)]()
[![WSL Compatible](https://img.shields.io/badge/WSL-ready-orange.svg)]()

</div>

---

## 📖 Overview

**RomVault** is a modular command-line tool designed for retro-gaming enthusiasts and collectors who prefer efficient, scriptable, and lightweight workflows. 

### Key Highlights
- **ES-DE Companion:** RomVault is built as a natural companion tool for the [ES-DE](https://es-de.org/) (EmulationStation Desktop Edition) retro-gaming frontend, tailored specifically to fit streamlined collection management workflows.
- **Efficient Organization:** It helps parse, sort, and maintain structured lists and inventories of your local ROM collections with precision.

### Legal Disclaimer
*RomVault is an independent utility designed to assist with local ROM management. It is not officially affiliated with, endorsed by, or connected to ES-DE, ScreenScraper, RetroAchievements, or any other third-party provider mentioned. All trademarks, service marks, and logos belong to their respective owners. RomVault operates strictly as a read-only companion tool and does not interfere with the native functionality, services, or servers of third-party platforms.
This project does not provide, host, distribute, promote, or encourage the sharing of ROMs, BIOS files, or any other copyrighted material. Users are strictly responsible for complying with local copyright laws and ensuring they only manage lawfully backed-up data.*

---

## ✨ Features

- **Advanced Collection Management:** Built specifically to streamline and parse your local ROM libraries with speed and precision, acting as the ideal backbone for your metadata and collection workflows.
- **Decoupled Configuration & Customization:** Cleanly separated architecture where configuration parameters and text strings are isolated into modular external files, keeping the core codebase untouched and user-customization straightforward.
- **Cross-Platform Compatibility:** Designed to run seamlessly on any system supporting Python, optimized for Linux and WSL environments where Windows-based retro-gaming paths can be accessed natively.
- **Multilingual Support:** Shipped natively with Italian and English localizations out of the box, with a flexible translation system that allows the community to easily expand or add new language maps.

---

## 🛠️ Project Structure

```text
RomVault/
├───────── Application files
├── romvault.py          # Core application script
├── romvault.art         # ASCII banner and logo resources
├── romvault.map         # Mapping and indexing definitions
├───────── Customizable files
├── romvault.lng         # Localization and string maps
├── romvault.cfg.example # Configuration template file
├───────── Optional files
└── romvault.sec         # Google Cloud's Integration API Key (details in the Wiki)
```

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/GenX-Hero/RomVault.git
cd RomVault
```

### 2. Configure the Environment
Copy the example configuration file and customize your local paths and settings:
```bash
cp romvault.cfg.example romvault.cfg
nano romvault.cfg
```

### 3. Run the Application
```bash
python3 romvault.py
```

---

# 🗺️ RomVault Roadmap (Toward v2.0)

This document outlines the future architectural milestones, advanced features, and core refactoring goals planned for RomVault v2.0.

---

### 🗄️ 1. Advanced Database Schema Evolution
* **Decoupled Mapping:** Move key system fields (such as `CRC32`, `MD5`, internal binaries) entirely into the mapping configuration file, making the core codebase completely agnostic of column structures.
* **Smart Migrations (`ALTER TABLE`):** Replace the destructive "drop and recreate" pattern with schema-diff analysis to add or remove columns while preserving existing historical user data.
* **Renaming Protection:** Introduce transition mapping or guided logic to handle column name changes safely without data loss.
* **Dynamic Queries:** Swap out hardcoded SQL string queries for parameterized ones driven by mapped tags (e.g., `SELECT {gamename} FROM roms`), ensuring future schema modifications do not break operational logic.
* **Safe Fallback Migration:** For major structural overhauls, implement safe table renaming, rebuilding, and known-data migration with user confirmation prompts.

---

### ⚡ 2. Upsert & Incremental Sync Evolution
* **Persistent Log Reports:** Extend the sync routine—currently outputting only screen statistics—to generate a dedicated file report (`VAR_REPORT_DIR`) detailing exactly which files were added, modified, or deleted system-by-system.
* **"Dry-Run" Preview Mode:** Introduce a simulation menu option to calculate and display delta changes *without* committing destructive `DELETE` operations or writes to the database.
* **Performance & Volume Handling:** Optimize recursive directory parsing and regex matching for massive collections, introducing granular transactional controls and responsive CLI feedback (progress bars/spinners).
* **XML Parser Decoupling:** Refine the mapping engine to ensure bulletproof robustness against malformed XML formatting generated by various third-party scrapers.

---

### 📺 3. Fullscreen Error Management
* Expand the intelligent error handling framework across all operational procedures, ensuring graceful recovery and clean 80x24 fallback dialogs when unexpected terminal states occur.

---

### 🏆 4. Native RetroAchievements Integration
* **API Export Synchronization:** Integrate a dedicated local table populated via API exports containing hashes of supported games.
* **Tag-Free Metadata:** Modify the `hasachi` flag injection logic to completely eliminate the need for custom tag appends (such as ` - (Y)`) directly inside ES-DE game names.

---

### 💿 5. Multi-Disc Media Management (`.m3u` Support)
* **Hybrid Resolution Engine:** Evaluate native `.m3u playlist parsing` as the standard ES-DE contract for multi-disc games, combining physical folder scanning as a fallback to maximize performance without imposing rigid folder structures on end-users.

---

### 🚦 6. Triage & Deep Auditing for Non-Cartridge Systems
* Extend the advanced heuristic triage and deep auditing pipelines—currently optimized for cartridge-based systems—to fully support optical disc-based and complex multi-file platforms.

---

## 📄 License

This project is licensed under the terms of the **GPL-3.0 License**. See the [LICENSE](LICENSE) file for details.
