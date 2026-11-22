# Installing GIBSON on Linux or WSL from GIBSON-MAINFRAME-COMPLETE.zip

This guide takes you from downloading `GIBSON-MAINFRAME-COMPLETE.zip` to a running GIBSON mainframe on Linux, or on Windows through WSL (Windows Subsystem for Linux). It covers unzipping the kit, installing it with `install_gibson.sh --venv`, granting the port capability, starting GIBSON with `gibsonctl.sh`, answering the IPL, and then taking a first look at the Master Console, the Pen-Test Shell and PHOSPHOR.

Every command in this guide is typed into a Linux terminal and followed by **Enter**, unless the step says otherwise.

---

## Contents

1. [What is GIBSON?](#1-what-is-gibson)
2. [What you need](#2-what-you-need)
3. [Windows only: setting up WSL](#3-windows-only-setting-up-wsl)
4. [Downloading the zip](#4-downloading-the-zip)
5. [Unzipping the kit](#5-unzipping-the-kit)
6. [Installing GIBSON with install_gibson.sh --venv](#6-installing-gibson-with-install_gibsonsh---venv)
7. [Granting the port capability](#7-granting-the-port-capability)
8. [Starting GIBSON with gibsonctl.sh](#8-starting-gibson-with-gibsonctlsh)
9. [IPLing the mainframe](#9-ipling-the-mainframe)
10. [The Master Console](#10-the-master-console)
11. [The web dashboard and web Master Console (port 8443)](#11-the-web-dashboard-and-web-master-console-port-8443)
12. [The Pen-Test Shell (port 8022)](#12-the-pen-test-shell-port-8022)
13. [A first look at PHOSPHOR](#13-a-first-look-at-phosphor)
14. [FTP and the USS shell](#14-ftp-and-the-uss-shell)
15. [Stopping, restarting and checking GIBSON](#15-stopping-restarting-and-checking-gibson)
16. [Default accounts, passwords and ports](#16-default-accounts-passwords-and-ports)
17. [Troubleshooting](#17-troubleshooting)
18. [Uninstalling](#18-uninstalling)

---

## 1. What is GIBSON?

GIBSON is a self-contained mainframe education and penetration-testing lab. At its heart is a simulated IBM z/OS-style mainframe, written in Python, that gives you a master console with a real IPL sequence, TSO logons over TN3270, an FTP server that understands datasets, a UNIX System Services (USS) shell, a RACF-style security database, JES2, DB2 and CICS-style services, a banking application with its own API, an SMTP listener, a zSecure-style alerting feed and a web dashboard, all running on one machine that you control and are free to break.

The kit also includes:

- **PHOSPHOR**, a TN3270 terminal emulator and mainframe audit toolkit, installed as the `phosphor` command.
- **The Pen-Test Shell**, a browser-based Linux shell with the course tools on its path (`ezrecon`, `zniff`, `cicspwn`, `tshocker`, `injector`, `nje-assess`, `njejcl`, `gibson-scan` and more), which wraps real tools such as `nmap`, `hydra`, `nikto` and John the Ripper.

Everything in the lab is deliberately fictional. The Pen-Test Shell's sandbox only allows targets in the lab itself (`127.0.0.1`, `localhost`, `::1` and the fictional `sighberbank.com` domain and its subdomains), so you can practise freely without any risk of touching a real system.

> **GIBSON is deliberately vulnerable.** By default it starts in its vulnerable training profile, with weak passwords and misconfigurations on purpose. Run it on your own machine or a lab virtual machine, and do not expose its ports to an untrusted network.

---

## 2. What you need

| Item | Requirement |
|---|---|
| Operating system | A 64-bit Linux distribution (Ubuntu 22.04 or 24.04, Debian 12, Kali and similar), or Windows 10 or 11 with WSL 2 running Ubuntu |
| Python | Python 3.10, 3.11 or 3.12 (the installer prefers these; 3.13 works, and 3.14 or later gives a warning) |
| Account | A normal user account that can use `sudo` |
| Disk space | About 1 GB free for GIBSON, its Python packages and its data, plus more if you install the Pen-Test Shell's security tools |
| Memory | 2 GB of free RAM or more |
| Internet | Needed during installation, to download Python packages |
| Tools | `unzip` and `setcap` (from `libcap2-bin`), which section 5 installs if they are missing |

---

## 3. Windows only: setting up WSL

If you are on Linux already, skip to [section 4](#4-downloading-the-zip).

WSL lets Windows run a real Linux system, and GIBSON installs into it exactly as it does on Linux. Microsoft's own documentation is the reference for installing WSL, because the steps change between Windows releases: see <https://learn.microsoft.com/windows/wsl/install>.

In short:

1. Click **Start**, type `PowerShell`, right-click **Windows PowerShell** and choose **Run as administrator**.
2. Type `wsl --install -d Ubuntu-24.04` and press **Enter**.
3. Restart Windows if you are asked to.
4. When Ubuntu opens for the first time, it asks you to create a **UNIX username** and a **password**. Choose both and remember the password, because `sudo` asks for it later in this guide.
5. From now on, open Ubuntu from the **Start** menu (type `Ubuntu` and press **Enter**) whenever this guide says "open a terminal".

> **Keep GIBSON inside the Linux file system.** Install GIBSON in your Linux home folder (`~`, which is `/home/<your-name>`), not under `/mnt/c/...`. The Windows drives that WSL shows under `/mnt/c` are slower and do not support the file capability that section 7 sets, so GIBSON would not be able to use ports 21 and 23 from there.

---

## 4. Downloading the zip

1. Open <https://github.com/kmilne40/GIBSON> in your web browser and click **Releases** on the right-hand side of the page.
2. Open the newest release and, under **Assets**, click `GIBSON-MAINFRAME-COMPLETE.zip` to download it.

You can also download it straight into your Linux home folder from a terminal:

```bash
cd ~
wget https://github.com/kmilne40/GIBSON/releases/latest/download/GIBSON-MAINFRAME-COMPLETE.zip
```

### WSL: copying a zip that you downloaded in Windows

If you downloaded the zip with a Windows browser, it is in your Windows **Downloads** folder. Copy it into your Linux home folder, replacing `YourWindowsName` with your Windows user name:

```bash
cp /mnt/c/Users/YourWindowsName/Downloads/GIBSON-MAINFRAME-COMPLETE.zip ~/
```

---

## 5. Unzipping the kit

1. Make sure the tools that the installation needs are present (on Ubuntu, Debian and Kali):

   ```bash
   sudo apt update
   sudo apt install -y unzip python3 python3-venv python3-pip libcap2-bin
   ```

   Type your Linux password when `sudo` asks for it. Nothing appears as you type it, which is normal.

2. Unzip the kit in your home folder and move into it:

   ```bash
   cd ~
   unzip GIBSON-MAINFRAME-COMPLETE.zip
   cd GIBSON-MAINFRAME-COMPLETE
   ```

3. Type `ls` to check what you have. The files that this guide uses are:

| File or folder | What it is |
|---|---|
| `install_gibson.sh` | The installer |
| `gibsonctl.sh` | Starts, stops and checks GIBSON |
| `scripts/grant-port-capabilities.sh` | Lets GIBSON use ports 21 and 23 without running as root |
| `scripts/install-pentest-tools.sh` | Installs or repairs the Pen-Test Shell's security tools |
| `gibson/` | The GIBSON simulator itself |
| `phosphor/` | The PHOSPHOR terminal and audit toolkit |
| `docs/guides/` | The GIBSON Mainframe Lab Guide and its chapters, as PDF and Word files |
| `START-HERE.md`, `README-BUILD.md` | Notes on the kit and on building the Windows, Mac and ISO versions |

The scripts keep their execute permission when you unzip with `unzip`. If you unzipped another way and a script says `Permission denied`, type `chmod +x install_gibson.sh gibsonctl.sh scripts/*.sh` and try again.

---

## 6. Installing GIBSON with install_gibson.sh --venv

The `--venv` option installs GIBSON and every Python package it needs into a private virtual environment, the `.venv` folder inside the kit, so nothing is added to your system Python.

1. Make sure you are in the kit folder (`cd ~/GIBSON-MAINFRAME-COMPLETE`), then type:

   ```bash
   ./install_gibson.sh --venv
   ```

2. The installer shows a blue banner and then works through these stages, each beginning with `==>`:
   - **Checking Python**, which prints the version it will use, then `[OK] Python ready`.
   - **Preparing virtual environment**. If your Python cannot create virtual environments, the installer installs `python3-venv` itself with `sudo apt-get`, so it may ask for your password here.
   - **Installing Gibson and Python dependencies**, which downloads and installs the packages. This is the longest stage and takes a few minutes. It ends with `Verified Python packages: flask ..., passlib ..., psutil ..., requests ..., websockets ...` and `[OK] Python packages installed`.
   - **Seeding simulator files**, which creates GIBSON's data folder, `~/mfsim`, and ends with `[OK] Simulator root prepared`.
   - **Pen-Test Shell security tools** (see the next step).
   - **Pen-Test Shell course tools**, which checks every course tool and should end with `13 of 13 course tools ready.`

3. During the **Pen-Test Shell security tools** stage, the installer explains that the Pen-Test Shell uses real `nmap`, `hydra`, `nikto`, `wget` and jumbo John the Ripper, and asks:

   ```text
   Install them now? [Y/n]
   ```

   Press **Enter** (or type `Y` and press **Enter**) to install them. This uses your package manager and `sudo`, can take between 5 and 30 minutes the first time (mostly building John the Ripper), and is the recommended choice. If you type `n` and press **Enter** instead, the lab still works and `nmap` falls back to the built-in `gibson-scan`, and you can install the tools later with `./scripts/install-pentest-tools.sh -y`. On Kali, where the tools are already installed, this stage passes silently.

4. The installer finishes with:

   ```text
   Installation complete.
   Next steps
     1. cd scripts
     2. sudo ./grant-port-capabilities.sh     (press ENTER, then move back up: cd ..)
     3. ./gibsonctl.sh start
     4. IPL - at the console, type each reply and press ENTER after each:
          R 01,CLPA
          R 02,U
          R 03,Y
          R 04,1234
          R 05,GIBSON
          R 06,1337
   ```

   The next three sections walk through those steps one at a time.

### Other installer options

Type `./install_gibson.sh --help` to see every option. The most useful are:

| Option | What it does |
|---|---|
| `--venv` | Install into `.venv` inside the kit (the default, and the one this guide uses) |
| `--pentest-tools` | Install the security tools without asking |
| `--no-pentest-tools` | Skip the security tools (install them later with `./scripts/install-pentest-tools.sh -y`) |
| `--python python3.12` | Use a particular Python, for example when your system Python is 3.14 |
| `--minimal` | Install only GIBSON's core packages, without the course tools' packages |
| `--sim-root PATH` | Keep GIBSON's data somewhere other than `~/mfsim` |

---

## 7. Granting the port capability

A real mainframe offers TSO on port 23 and FTP on port 21, and GIBSON does the same. Linux only lets root use ports below 1024, so rather than running all of GIBSON as root, this step gives the Python interpreter that runs GIBSON one narrow permission (`CAP_NET_BIND_SERVICE`) that lets it use those ports while running as you. You only need to do this once.

1. Move into the `scripts` folder:

   ```bash
   cd scripts
   ```

2. Run the script with `sudo`, giving it the virtual environment's Python so that the permission is granted to exactly the interpreter that GIBSON uses:

   ```bash
   sudo ./grant-port-capabilities.sh ../.venv/bin/python
   ```

   You can also type `sudo ./grant-port-capabilities.sh` on its own, as the installer suggests, and on most systems that grants the same interpreter. Naming `../.venv/bin/python` is the safer form, because on a machine with more than one Python installed the plain form can grant the wrong one, and GIBSON would then still be refused ports 21 and 23.

3. The script prints which interpreter it granted and checks the result, for example:

   ```text
   Granting CAP_NET_BIND_SERVICE to: /usr/bin/python3.12
   Verifying:
   /usr/bin/python3.12 cap_net_bind_service=ep

   Done. /usr/bin/python3.12 may now bind ports below 1024 (23, 21) without root.
   ```

   The line ending in `cap_net_bind_service=ep` is the one that matters.

4. Move back up to the kit folder:

   ```bash
   cd ..
   ```

> **When to run it again.** The permission belongs to the Python program file, so if a system update replaces Python, run step 2 again. If `setcap` is not found, install it with `sudo apt install -y libcap2-bin`.

---

## 8. Starting GIBSON with gibsonctl.sh

Always run `gibsonctl.sh` from inside the kit folder, because it uses the folder you are in to find GIBSON's virtual environment and to keep its process and log files.

1. Make sure you are in the kit folder, then start GIBSON:

   ```bash
   cd ~/GIBSON-MAINFRAME-COMPLETE
   ./gibsonctl.sh start
   ```

2. If you skipped the security tools during installation, `gibsonctl.sh` offers them once more at this point with the same `Install them now? [Y/n]` question, and after that only prints a one-line reminder of how to install them.

3. GIBSON then starts its IPL in your terminal and waits for your replies. Carry on with [section 9](#9-ipling-the-mainframe).

---

## 9. IPLing the mainframe

An IPL (initial program load) is how a z/OS system is started, and the operator answers a short series of numbered requests at the master console. GIBSON asks for the same replies every time you start it.

1. The terminal shows the GIBSON control panel and the first request:

   ```text
   IEA794I IBM Z/OS MASTER CONSOLE CONS01 ACTIVE FOR SYSTEM GIB1 AT 2026.326 22:42:18
   IEA168I GIBSON IPL INITIATED - NUCLEUS INITIALIZATION PROGRAM ACTIVE

   IEE600I REPLY TO OUTSTANDING IPL REQUESTS WITH R nn,answer
   IEE112I 22.42.18 PENDING REQUESTS
   R 01 IEA101A SPECIFY SYSTEM PARAMETERS FOR RELEASE z/OS 03.02.00

   MASTER CONSOLE REPLY ===>
   ```

2. Type each reply below at the `MASTER CONSOLE REPLY ===>` prompt and press **Enter**, waiting for the next request to appear before you type the next reply:

| You type | GIBSON is asking | What the reply means |
|---|---|---|
| `R 01,CLPA` | `IEA101A SPECIFY SYSTEM PARAMETERS` | Build the link pack area afresh (a "cold" start of the system code) |
| `R 02,U` | `IEA347A REPLY U TO USE DEFAULT IEASYS00` | Use the default system parameters member, IEASYS00 |
| `R 03,Y` | `IEA102A REPLY Y TO CONTINUE GIBSON IPL` | Carry on with the IPL; JES2, RACF, OMVS and TCP/IP then start |
| `R 04,1234` | `R 04 DEFINE 4-DIGIT MFA PIN FOR THIS IPL` | Sets the operator MFA PIN for this IPL; when MFA is on, the token is the PIN followed by the time as HHMM |
| `R 05,GIBSON` | `R 05 IEE600A REPLY 05 WITH SYSTEM HOSTNAME` | Names the system GIBSON, which also points the name GIBSON at 127.0.0.1 |
| `R 06,1337` | `R 06 DEFINE 4-DIGIT DVCAPIN OR SKIP` | Sets the training PIN for the DVCA, CBSA and OMEN banking labs; type `R 06,SKIP` instead if you do not need it |

3. After the last reply, GIBSON prints `GIBMCS012I IPL REPLY SEQUENCE COMPLETE - SERVICES MAY START`, starts its services and reports the process number and log file, for example:

   ```text
   Started Gibson PID 639
   Log: /home/you/GIBSON-MAINFRAME-COMPLETE/logs/gibson.log
   Opening GIBSON MASTER CONSOLE. Use QUIT, EXIT, F12 or Q to leave.
   GIBSON services will continue running after the console exits.
   ```

> **Lines about web3270 or a browser terminal on port 8023.** The optional web3270 browser 3270 terminal needs Docker and an extra download. If it is not set up, `gibsonctl.sh` prints messages such as `Browser terminal helper not found` or `web3270: setup failed (needs git/network) - skipped`, which you can ignore, because every other part of GIBSON works without it.

---

## 10. The Master Console

When the IPL is finished, `gibsonctl.sh` opens the GIBSON MASTER CONSOLE in your terminal. It has an **OPERLOG / ALERT STREAM** on the left, which shows console messages and security alerts as they happen, a **SYSTEM PROCESSING** panel on the right, which should show `IPL COMPLETE` with JES2, VTAM, CICS, DB2 and USS `ACTIVE` and TSO `READY`, and a `COMMAND ===>` line at the bottom.

1. Type `D A,L` and press **Enter** to display the active address spaces (JES2, RACF, TCPIP, TN3270, FTPD, CICS, the DB2 subsystem and the rest).
2. Press **F7** or **Page Up** and **F8** or **Page Down** to scroll the log, and **Ctrl+L** to redraw the screen.
3. To leave the console, type `QUIT` and press **Enter**, or press **F12**, or type `Q` and press **Enter**. GIBSON keeps running in the background after you leave.
4. To open the console again later, go to the kit folder and type `./gibsonctl.sh master`.

The same console is also in your browser, as the next section shows.

---

## 11. The web dashboard and web Master Console (port 8443)

GIBSON's operations dashboard and a web version of the Master Console are served on port 8443 over plain HTTP.

1. Open your web browser and go to <http://localhost:8443/>. On WSL, use a browser in Windows; WSL passes `localhost` through to Linux.
2. Your browser asks you to sign in. Type the following and click **Sign in**:

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `gibsonadmin!` |

3. The **I3M Gibson Mainframe Operations Dashboard** shows active and recent users, the number of RACF users and JES jobs, a recent audit log of SMF records, a system summary, a map of connections, and the status of every service. Security alerts (zSecure-style messages such as `C2P1213A`) pop up in red at the top right, and you can close each one with its **x** button.
4. Click **Master Console** in the menu at the top of the page, or go to <http://localhost:8443/console>, to open the web Master Console. Its header should say **IPL complete - system up**.
5. Click in the command box at the bottom, type a command such as `D A,L` and press **Enter**. The row of buttons under the header (`R 01,CLPA`, `R 02,U`, `R 03,Y`, `R 05,GIBSON`, `R 06,SKIP`, `D A,L`, `D R,R` and `? help`) types the common replies and commands for you.

> **Changing the dashboard password.** The dashboard and the Pen-Test Shell share one login, which you can change by setting it before you start GIBSON, for example `export GIBSON_DASHBOARD_USER=admin` and `export GIBSON_DASHBOARD_PASSWORD='a-new-password'` and then `./gibsonctl.sh restart`.

---

## 12. The Pen-Test Shell (port 8022)

The Pen-Test Shell is a Linux terminal in your browser, with the course tools on its path and a sandbox that only lets them reach the lab. It listens only on `127.0.0.1`, so it can only be opened from the machine that runs GIBSON.

1. Go to <http://localhost:8022/>, or click **Pen-Test Shell** in the dashboard's menu.
2. Sign in with the same login as the dashboard:

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `gibsonadmin!` |

3. The shell shows a banner that lists the **AUTHORISED TARGETS ONLY** (`127.0.0.1`, the local GIBSON lab, and `sighberbank.com`, the educational FIBS bank), the wordlists in `./wordlists/` (`users.txt`, `passwords.txt`, `subdomains.txt`, `domains.txt` and `wordlist.txt`), and the course tools, and ends with a `gibson-pentest:~$` prompt.
4. Try these commands, pressing **Enter** after each:

| Command | What it does |
|---|---|
| `scope` | Shows the targets the sandbox allows |
| `tools` | Lists every tool in the shell, with an example for each |
| `tool-check` | Checks that every course tool is ready, and says how to fix any that is not |
| `gibson-scan 127.0.0.1 -sV` | Scans the lab with GIBSON's built-in scanner, which needs nothing extra installed |
| `nmap 127.0.0.1` | Scans the lab with the real nmap, if you installed the security tools |
| `phosphor 127.0.0.1 --client` | Opens PHOSPHOR's 3270 terminal inside the browser shell |

Any target that is not in the allowlist is refused by the sandbox, so `nmap 8.8.8.8`, for example, is blocked.

---

## 13. A first look at PHOSPHOR

PHOSPHOR is a TN3270 terminal emulator and mainframe audit toolkit that is installed with GIBSON. Its `--client` mode runs in any terminal and behaves like `c3270`.

1. Open a second terminal (on WSL, open another Ubuntu window), go to the kit folder and switch on GIBSON's virtual environment so that the `phosphor` command is available:

   ```bash
   cd ~/GIBSON-MAINFRAME-COMPLETE
   source .venv/bin/activate
   ```

   Your prompt now begins with `(.venv)`. You can also run PHOSPHOR without activating the environment, by typing `.venv/bin/phosphor` in place of `phosphor`.

2. Connect to GIBSON's TN3270 port:

   ```bash
   phosphor 127.0.0.1 23 --client
   ```

3. The GIBSON PRODUCTION LPAR logon screen appears, with the warning banner, your LU name and client address, and the line `LOGON using L TSO, L CICS, L DB2, L IMS, L ZVM or L TPF.` with the cursor at `Logon Type:`. Type `L TSO` and press **Enter**.
4. The **TSO/E LOGON** panel appears with the cursor in the `Userid ===>` field. Type `IBMUSER`, press **Tab** to move to the `Password ===>` field, type `SYS1`, and press **Enter**.
5. GIBSON shows `ICH70001I IBMUSER LAST ACCESS AT ...`, the GIBSON z/OS SECURITY TRAINING SYSTEM banner and `READY`. You are now at the TSO prompt.
6. Type `LISTCAT` and press **Enter** to list IBMUSER's datasets (`IBMUSER.JCL.LAB`, `IBMUSER.REXX.LAB`, `IBMUSER.MAIL.IN` and others). Press **F8** to page down and **F7** to page up.
7. Type `LOGOFF` and press **Enter** to log off, which returns you to the logon screen.
8. Type `:q` and press **Enter** to leave PHOSPHOR.

While you are in PHOSPHOR, the line at the bottom of the screen reminds you of the keys: the function keys send PF keys, **Tab** moves between fields, **Enter** sends the screen, **Ctrl+K** opens an on-screen keypad (for PA1, PA2, Clear and the rest), and **:** opens PHOSPHOR's own command line, where `:q` quits and `:menu` offers file transfers and FTP.

Notice that the Master Console's alert stream logs your logon as it happens, with messages such as `*TSO LOGON ALERT: IBMUSER signed on to TSO from 127.0.0.1`, which is the defender's view of what you have just done.

### Other PHOSPHOR modes

| Command | What it does |
|---|---|
| `phosphor 127.0.0.1 23 --client --repl` | A simple line-by-line prompt instead of the full-screen terminal |
| `phosphor 127.0.0.1 --gui` | The PHOSPHOR desktop app; needs a graphical desktop (on WSL, Windows 11's WSLg provides one) |
| `phosphor 127.0.0.1 --scan --yes` | The recon audit suite; needs the unlock code from the *Hacking Mainframes* book, given with `--unlock CODE` |
| `phosphor 127.0.0.1 --menu --yes` | The interactive recon menu; also needs the unlock code |
| `phosphor --help` | Every option |

---

## 14. FTP and the USS shell

**FTP (port 21).** Type `ftp 127.0.0.1` and press **Enter** (install the client first with `sudo apt install -y ftp` if it is missing). GIBSON answers with `220-GIBSON IBM FTP CS V3R2 at GIBSON`. Sign in with the name `IBMUSER` and the password `SYS1`, type `dir` and press **Enter** to list datasets, and type `bye` and press **Enter** to leave.

**USS shell (port 2022).** Type `telnet 127.0.0.1 2022` and press **Enter** (install the client first with `sudo apt install -y telnet` if it is missing). At `login:` type `IBMUSER`, at `Password:` type `SYS1`, and you arrive at an `IBMUSER:/u/ibmuser$` prompt in GIBSON's z/OS UNIX System Services. Type `exit` and press **Enter** to leave.

---

## 15. Stopping, restarting and checking GIBSON

Run every one of these from the kit folder (`cd ~/GIBSON-MAINFRAME-COMPLETE`):

| Command | What it does |
|---|---|
| `./gibsonctl.sh status` | Shows whether GIBSON is running, and its process |
| `./gibsonctl.sh stop` | Stops GIBSON |
| `./gibsonctl.sh stop --force` | Stops GIBSON forcibly, if a normal stop does not work |
| `./gibsonctl.sh restart` | Stops and starts GIBSON (you answer the IPL again) |
| `./gibsonctl.sh master` | Opens the terminal Master Console again |
| `./gibsonctl.sh start --no-master` | Starts GIBSON without opening the terminal console afterwards |
| `./gibsonctl.sh start --secure` | Starts the hardened, CIS-aligned profile instead of the vulnerable one (TSO then moves to port 1023 and the dashboard to HTTPS on 8443) |
| `./gibsonctl.sh smtp-check` | Shows where the mail listener is and, if it is not listening, why |
| `./gibsonctl.sh help` | Lists every action and option |

GIBSON's log is `logs/gibson.log` in the kit folder, and its simulated mainframe data (RACF database, DASD, spool and audit logs) is in `~/mfsim`. To follow the log as it is written, type `tail -f logs/gibson.log`, and press **Ctrl+C** to stop following it.

On WSL, GIBSON stops when WSL shuts down (for example when Windows restarts), so you start it again with `./gibsonctl.sh start` the next time you open Ubuntu.

---

## 16. Default accounts, passwords and ports

These are lab accounts for a fictional system, published so that everyone starts from the same place.

| Where | Username | Password |
|---|---|---|
| Web dashboard and web Master Console, <http://localhost:8443/> | `admin` | `gibsonadmin!` |
| Pen-Test Shell, <http://localhost:8022/> | `admin` | `gibsonadmin!` |
| TSO (port 23), FTP (port 21) and USS (port 2022) | `IBMUSER` | `SYS1` |
| IPL replies | MFA PIN `1234` | DVCA PIN `1337` (or `SKIP`) |

| Port | Service |
|---|---|
| 21 | FTP, dataset-aware (IBM FTP CS) |
| 23 | TN3270: VTAM logon screen, TSO, CICS and the rest |
| 80 | Welcome to Gibson page |
| 175 | NJE (network job entry) |
| 446 | DB2 DRDA |
| 2022 | USS terminal |
| 2252 | NJE over TLS |
| 2525 | SMTP listener (IBM MVS SMTP; receives mail, never relays) |
| 8022 | Pen-Test Shell (127.0.0.1 only) |
| 8080 | Unified CBSA, DVCA and hack3270 banking application server (it presents itself as Apache Tomcat) |
| 8443 | Operations dashboard and web Master Console (HTTP) |
| 9080 | FIBS Bank, the First International Bank of Scotland web application |
| 50001 | DB2 web service |

---

## 17. Troubleshooting

**`Permission denied` when GIBSON tries to use port 21 or 23.**
The port capability is missing or was given to a different Python. Go to the kit folder and run `sudo ./scripts/grant-port-capabilities.sh .venv/bin/python`, then `./gibsonctl.sh restart`. On WSL, also check that the kit is in your Linux home folder and not under `/mnt/c`.

**The installer says it cannot create a virtual environment.**
Install the venv package for your Python, for example `sudo apt install -y python3-venv` (or `python3.12-venv`), and run `./install_gibson.sh --venv` again.

**The installer warns that the course tools are tested on Python 3.10 to 3.12.**
Your system Python is newer. Install Python 3.12 if your distribution offers it, delete the `.venv` folder (`rm -rf .venv`), and run `./install_gibson.sh --venv --python python3.12`.

**`./gibsonctl.sh stop` says the process is `still alive`.**
GIBSON can take a few seconds to shut down. Wait a moment and type `./gibsonctl.sh status`; if it is still running, type `./gibsonctl.sh stop --force`.

**`./gibsonctl.sh status` lists every port as `free` while GIBSON is running.**
The status check uses `ss`, `lsof` or `fuser` to look at ports. Install one of them with `sudo apt install -y iproute2 lsof` to see the real picture.

**The browser cannot reach localhost:8443 on WSL.**
Check that GIBSON is running (`./gibsonctl.sh status`). If it is, and Windows still cannot reach it, type `wsl --shutdown` in a Windows PowerShell window, open Ubuntu again, start GIBSON again, and try once more. Microsoft's WSL networking documentation explains the `localhost` forwarding settings.

**A Pen-Test Shell tool reports NOT READY, or nmap uses gibson-scan.**
Type `tool-check` in the Pen-Test Shell to see what is missing, and install or repair the security tools from the kit folder with `./scripts/install-pentest-tools.sh -y`.

**A port is already in use.**
Another program (or an earlier copy of GIBSON) is using it. Type `./gibsonctl.sh stop --force`, then `sudo ss -ltnp | grep -E ':(21|23|8443|8022) '` to see what is still holding the port.

---

## 18. Uninstalling

1. Stop GIBSON from the kit folder with `./gibsonctl.sh stop`.
2. Remove the port capability from the interpreter that you granted it to:

   ```bash
   sudo setcap -r "$(readlink -f ~/GIBSON-MAINFRAME-COMPLETE/.venv/bin/python)"
   ```

3. Delete the kit and GIBSON's data:

   ```bash
   rm -rf ~/GIBSON-MAINFRAME-COMPLETE ~/mfsim
   ```

The security tools installed by `install-pentest-tools.sh` (nmap, hydra, nikto and the rest) are ordinary system packages and stay installed, and you can remove them with your package manager if you no longer need them.
