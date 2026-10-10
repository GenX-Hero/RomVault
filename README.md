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
*RomVault is an independent management utility. This project does not provide, host, distribute, promote, or encourage the sharing of ROMs, BIOS files, or any other copyrighted material. Users are strictly responsible for complying with local copyright laws and ensuring they only manage lawfully backed-up data.*

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

## 📄 License

This project is licensed under the terms of the **GPL-3.0 License**. See the [LICENSE](LICENSE) file for details.
