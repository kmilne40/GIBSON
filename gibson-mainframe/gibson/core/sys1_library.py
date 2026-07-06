"""Authentic SYS1 system-library content for Gibson.

The members below mirror what a z/OS systems programmer would expect to find in
the core SYS1 libraries on a running system: the PARMLIB members that drive IPL
and subsystem configuration, the PROCLIB started-task procedures, the VTAMLST
network definitions, and the TCP/IP profile/resolver members. Values are
realistic for a single-image training LPAR named GIBSON (sysplex GIBPLEX,
SYSRES SBSYS1) and are internally consistent (the data set names, volumes,
ports, and subsystem names cross-reference each other the way a real system's
do).

Content is plain-text z/OS configuration (the same format documented in the IBM
z/OS MVS Initialization and Tuning Reference, JES2 Init & Tuning Reference,
Communications Server IP Configuration Reference, and VTAM Resource Definition
Reference). It is training/reference material - there are no real credentials,
keys, or load modules here; load-module and macro libraries keep representative
directory entries with a short placeholder note, since their real content is
binary object code.

``DatasetCatalog`` merges this dict over its built-in ``SYSTEM_DATASETS`` so the
enriched libraries override the older thin placeholders. Static text libraries
carry ``"refresh": True`` so that a re-seed upgrades any stale placeholder
members already on disk to this canonical content (dynamic data sets such as
SYS1.RACFDS / SYS1.MANx are intentionally not included here and keep their
runtime-managed behaviour).
"""
from __future__ import annotations

VOL_SYSRES = "SBSYS1"

# A short, honest note used in place of binary object code for load-module and
# macro libraries (their real members are link-edited modules, not text).
_LOADMOD = "* LOAD MODULE (link-edited object code) - directory entry only\n"
_MACRO = "* ASSEMBLER MACRO SOURCE - directory entry\n"


SYS1_SYSTEM_DATASETS: dict = {

    # ------------------------------------------------------------------ #
    #  SYS1.IPLPARM - LOADxx the IPL uses to find PARMLIB, IODF, catalog  #
    # ------------------------------------------------------------------ #
    "SYS1.IPLPARM": {
        "ORG": "PO", "VOLUME": VOL_SYSRES, "refresh": True,
        "members": {
            "LOAD00": (
                "IODF     01 SYS1                            GIBSON   00\n"
                "SYSCAT   SBCAT1113CSYS1.ICFCAT.MASTER\n"
                "SYSPARM  00\n"
                "IEASYM   00\n"
                "NUCLST   00\n"
                "NUCLEUS  1\n"
                "SYSPLEX  GIBPLEX\n"
                "PARMLIB  USER.PARMLIB                       SBUSR1\n"
                "PARMLIB  SYS1.PARMLIB                       SBSYS1\n"
            ),
            "NUCLST00": (
                "* NUCLST00 - nucleus module selection\n"
                "SELECT MODID(IEANUC01)\n"
            ),
        },
    },

    # ------------------------------------------------------------------ #
    #  SYS1.PARMLIB - the heart of system configuration                  #
    # ------------------------------------------------------------------ #
    "SYS1.PARMLIB": {
        "ORG": "PO", "VOLUME": VOL_SYSRES, "refresh": True,
        "members": {
            # Master member - read first at IPL; points at the xx members.
            "IEASYS00": (
                "SYSNAME=GIBSON,\n"
                "SYSP=(00),\n"
                "CLOCK=00,\n"
                "CMD=00,\n"
                "CON=00,\n"
                "COUPLE=00,\n"
                "GRS=STAR,\n"
                "GRSCNF=00,\n"
                "GRSRNL=00,\n"
                "GRSRNL=EXCLUDE,\n"
                "GRS=NONE,\n"
                "GRS=TRYJOIN,\n"
                "IOS=00,\n"
                "GRS=START,\n"
                "LNK=00,\n"
                "LNKAUTH=APFTAB,\n"
                "LPA=00,\n"
                "MAXUSER=512,\n"
                "MLPA=00,\n"
                "OMVS=00,\n"
                "OPI=YES,\n"
                "OPT=00,\n"
                "PAGE=(PAGE.GIBSON.PLPA,\n"
                "      PAGE.GIBSON.COMMON,\n"
                "      PAGE.GIBSON.LOCAL1,L),\n"
                "PLEXCFG=MONOPLEX,\n"
                "PROG=00,\n"
                "RSU=0,\n"
                "SCH=00,\n"
                "SMF=00,\n"
                "SSN=00,\n"
                "SVC=00,\n"
                "VAL=00\n"
            ),
            # System symbols.
            "IEASYM00": (
                "SYSDEF SYSCLONE(&SYSNAME(1:2).)\n"
                "       SYMDEF(&SYSR1='SBSYS1')\n"
                "       SYMDEF(&SYSPLEX.='GIBPLEX')\n"
                "       SYMDEF(&JOBNAME.='&JOBNAME.')\n"
            ),
            # IPL configuration (LOADxx also kept in PARMLIB for convenience).
            "LOAD00": (
                "IODF     01 SYS1                            GIBSON   00\n"
                "SYSCAT   SBCAT1113CSYS1.ICFCAT.MASTER\n"
                "SYSPARM  00\n"
                "IEASYM   00\n"
                "NUCLEUS  1\n"
                "SYSPLEX  GIBPLEX\n"
                "PARMLIB  SYS1.PARMLIB                       SBSYS1\n"
            ),
            # TOD clock / time zone.
            "CLOCK00": (
                "OPERATOR NOPROMPT\n"
                "TIMEZONE W.00.00.00\n"
                "ETRMODE  YES\n"
                "ETRZONE  YES\n"
                "SIMETRID 00\n"
            ),
            # Commands issued automatically at the end of IPL.
            "COMMND00": (
                "COM='START JES2'\n"
                "COM='START VTAM,,,(LIST=00)'\n"
                "COM='START TCPIP'\n"
                "COM='START TN3270'\n"
                "COM='START OMVS'\n"
                "COM='START LLA,SUB=MSTR'\n"
                "COM='START VLF,SUB=MSTR'\n"
                "COM='START RACF'\n"
                "COM='START FTPD,JOBNAME=FTPD1'\n"
                "COM='SET SMF=00'\n"
            ),
            # MCS console definitions.
            "CONSOL00": (
                "CONSOLE DEVNUM(01F)\n"
                "        NAME(GIBMSTR)\n"
                "        AUTH(MASTER)\n"
                "        ROUTCODE(ALL)\n"
                "        LEVEL(ALL)\n"
                "        MSCOPE(*ALL)\n"
                "        PFKTAB(PFKTAB00)\n"
                "INIT    AMRF(Y)\n"
                "        MONITOR(JOBNAMES-T,SESS-T)\n"
                "        CMDDELIM(;)\n"
                "        PFK(00)\n"
                "DEFAULT ROUTCODE(ALL) LEVEL(R,I,CE,E,IN)\n"
                "HARDCOPY DEVNUM(SYSLOG)\n"
                "        ROUTCODE(ALL)\n"
                "        CMDLEVEL(CMDS)\n"
            ),
            # Sysplex / XCF couple data sets (monoplex here).
            "COUPLE00": (
                "COUPLE  SYSPLEX(GIBPLEX)\n"
                "        PCOUPLE(SYS1.XCF.CDS01,SBXCF1)\n"
                "        ACOUPLE(SYS1.XCF.CDS02,SBXCF2)\n"
                "        INTERVAL(85)\n"
                "        OPNOTIFY(88)\n"
                "        MAXMSG(2000)\n"
                "        CLEANUP(60)\n"
                "LOCALMSG MAXMSG(2000) CLASS(DEFAULT)\n"
            ),
            # Global resource serialization.
            "GRSCNF00": (
                "MATCHSYS(*)\n"
                "RNLREFRESH(YES)\n"
                "TOLINT(180)\n"
                "CTRACE(CTIGRS00)\n"
            ),
            "GRSRNL00": (
                "RNLDEF RNL(INCL) TYPE(GENERIC) QNAME(SYSDSN)\n"
                "RNLDEF RNL(EXCL) TYPE(GENERIC) QNAME(SYSDSN) RNAME(SYS1.BRODCAST)\n"
                "RNLDEF RNL(INCL) TYPE(GENERIC) QNAME(SYSVTOC)\n"
                "RNLDEF RNL(CON)  TYPE(GENERIC) QNAME(SYSIGGV2)\n"
            ),
            # SRM/WLM tuning.
            "IEAOPT00": (
                "MCCAFCTH=(400,600)\n"
                "RMPTTOM=3000\n"
                "ERV=500\n"
                "CCCAWMT=3200\n"
                "HIPERDISPATCH=YES\n"
                "BLWLTRPCT=5\n"
            ),
            # I/O supervisor / MIH.
            "IECIOS00": (
                "MIH TIME=00:15,DEV=(0000-FFFF)\n"
                "HOTIO IOTIMING=ON\n"
                "MIH IOTIMING=01:00,DEV=(0900-09FF)\n"
            ),
            # User SVC table.
            "IEASVC00": (
                "* No installation SVCs defined on this training system.\n"
                "* SVC 200-255 reserved for installation use.\n"
            ),
            # Subsystem definitions (order matters: primary JES first).
            "IEFSSN00": (
                "SUBSYS SUBNAME(JES2) PRIMARY(YES) START(YES)\n"
                "SUBSYS SUBNAME(SMS) INITRTN(IGDSSIIN) INITPARM('ID=00,PROMPT=DISPLAY')\n"
                "SUBSYS SUBNAME(RACF)\n"
                "SUBSYS SUBNAME(OMVS)\n"
                "SUBSYS SUBNAME(STC)\n"
                "SUBSYS SUBNAME(DB2D) INITRTN(DSN3INI) INITPARM('DSN3EPX,-DB2D,S')\n"
                "SUBSYS SUBNAME(IRLM)\n"
            ),
            # TSO/E authorized commands and programs.
            "IKJTSO00": (
                "AUTHCMD NAMES(  /* AUTHORIZED COMMANDS */ +\n"
                "  LISTBC   LISTB    PARMLIB  RACONVRT +\n"
                "  SEND     OPER     CONSOLE  SYNC     +\n"
                "  RACDCERT RACFRW   TARGET   ACCOUNT  +\n"
                "  ADDSD    ALTDSD   DELDSD   PERMIT   +\n"
                "  ADDUSER  ALTUSER  DELUSER  LISTUSER +\n"
                "  ADDGROUP ALTGROUP DELGROUP LISTGRP  +\n"
                "  RDEFINE  RALTER   RDELETE  RLIST    +\n"
                "  SETROPTS SEARCH   RVARY)\n"
                "\n"
                "AUTHPGM  NAMES(  /* AUTHORIZED PROGRAMS */ +\n"
                "  IKJEFT01 IKJEFT1A IKJEFT1B IRXJCL   +\n"
                "  IEBCOPY  IDCAMS   ICKDSF)\n"
                "\n"
                "AUTHTSF  NAMES(  /* AUTH VIA TSO SERVICE FACILITY */ +\n"
                "  IKJEFF76 IRXJCL   IEBCOPY)\n"
                "\n"
                "NOTBKGND NAMES(  /* NOT IN BACKGROUND */ +\n"
                "  CONSOLE  OPER)\n"
            ),
            # LNKLST concatenation (also definable via PROGxx).
            "LNKLST00": (
                "SYS1.LINKLIB\n"
                "SYS1.MIGLIB\n"
                "SYS1.CSSLIB\n"
                "SYS1.SIEALNKE\n"
                "SYS1.SIEAMIGE\n"
                "CEE.SCEERUN\n"
                "CEE.SCEERUN2\n"
                "TCPIP.SEZALOAD\n"
                "ISP.SISPLOAD\n"
            ),
            # PLPA library list.
            "LPALST00": (
                "SYS1.LPALIB\n"
                "SYS1.SIEALNKE\n"
                "CEE.SCEELPA\n"
                "ISP.SISPLPA\n"
            ),
            "MLPA00": (
                "* MLPA00 - modified link pack area (test modules only)\n"
                "INCLUDE LIBRARY(SYS1.LPALIB) MODULES()\n"
            ),
            # Master scheduler JCL (kept in PARMLIB on modern z/OS).
            "MSTJCL00": (
                "//MSTJCL00 JOB MSGLEVEL=(1,1),TIME=1440\n"
                "//STARTING EXEC PGM=IEEMB860\n"
                "//STCINRDR DD SYSOUT=(A,INTRDR)\n"
                "//TSOINRDR DD SYSOUT=(A,INTRDR)\n"
                "//IEFPDSI  DD DSN=SYS1.PROCLIB,DISP=SHR\n"
                "//         DD DSN=CPAC.PROCLIB,DISP=SHR\n"
                "//SYSUADS  DD DSN=SYS1.UADS,DISP=SHR\n"
                "//SYSLBC   DD DSN=SYS1.BRODCAST,DISP=SHR\n"
            ),
            # Authorized program facility / LNKLST / LPA / exits (dynamic APF).
            "PROG00": (
                "APF FORMAT(DYNAMIC)\n"
                "APF ADD DSNAME(SYS1.LINKLIB)  VOLUME(SBSYS1)\n"
                "APF ADD DSNAME(SYS1.SVCLIB)   VOLUME(SBSYS1)\n"
                "APF ADD DSNAME(SYS1.MIGLIB)   VOLUME(SBSYS1)\n"
                "APF ADD DSNAME(SYS1.CSSLIB)   VOLUME(SBSYS1)\n"
                "APF ADD DSNAME(SYS1.SIEALNKE) VOLUME(SBSYS1)\n"
                "APF ADD DSNAME(SYS1.SIEAMIGE) VOLUME(SBSYS1)\n"
                "APF ADD DSNAME(TCPIP.SEZALOAD) VOLUME(SBPRD1)\n"
                "APF ADD DSNAME(TCPIP.SEZATCP)  VOLUME(SBPRD1)\n"
                "APF ADD DSNAME(ISP.SISPLOAD)   VOLUME(SBPRD1)\n"
                "APF ADD DSNAME(SYS1.SDSF.SISFLOAD) VOLUME(SBPRD1)\n"
                "\n"
                "LNKLST DEFINE NAME(LNKLST00)\n"
                "LNKLST ADD NAME(LNKLST00) DSNAME(SYS1.LINKLIB)\n"
                "LNKLST ADD NAME(LNKLST00) DSNAME(SYS1.MIGLIB)\n"
                "LNKLST ADD NAME(LNKLST00) DSNAME(SYS1.CSSLIB)\n"
                "LNKLST ADD NAME(LNKLST00) DSNAME(CEE.SCEERUN)\n"
                "LNKLST ADD NAME(LNKLST00) DSNAME(TCPIP.SEZALOAD)\n"
                "LNKLST ACTIVATE NAME(LNKLST00)\n"
                "\n"
                "EXIT ADD EXITNAME(SYS.IEFACTRT) MODNAME(ACTRTGIB)\n"
                "EXIT ADD EXITNAME(SYSSTC.IEFUJI) MODNAME(IEFUJIGB) STATE(ACTIVE)\n"
            ),
            # Program properties table / abend recovery.
            "SCHED00": (
                "PPT PGMNAME(IEFIIC)   NOCANCEL KEY(7)\n"
                "PPT PGMNAME(IEEMB860) NOCANCEL KEY(0) SYST NOPREFTCH PRIV\n"
                "PPT PGMNAME(HASJES20) NOCANCEL KEY(1) SYST NOSWAP PRIV\n"
                "PPT PGMNAME(ISTINM01) NOCANCEL KEY(6) SYST NOSWAP\n"
                "PPT PGMNAME(EZBTCPIP) NOCANCEL KEY(6) SYST NOSWAP\n"
                "PPT PGMNAME(BPXVCLNY) NOCANCEL KEY(0) SYST NOSWAP PRIV\n"
                "PPT PGMNAME(DFHSIP)   KEY(8)\n"
                "PPT PGMNAME(DSNYASCP) NOCANCEL KEY(7) SYST\n"
            ),
            # SMF parameters - keep RECORDING(DATASET) + SYS1.MANx (test invariant).
            "SMFPRM00": (
                "ACTIVE\n"
                "RECORDING(DATASET)\n"
                "DSNAME(SYS1.MANA,SYS1.MANB,SYS1.MANC)\n"
                "MAXDORM(3000)\n"
                "STATUS(010000)\n"
                "JWT(0030)\n"
                "SID(GIBS)\n"
                "LISTDSN\n"
                "SYS(NOTYPE(14,15,18,62,69),EXITS(IEFU83,IEFU84,IEFACTRT),\n"
                "    INTERVAL(SMF,SYNC),DETAIL)\n"
                "SUBSYS(STC,EXITS(IEFU29,IEFU83,IEFU84,IEFACTRT),\n"
                "    INTERVAL(SMF,SYNC))\n"
                "SUBSYS(TSO,TYPE(7,30,80,83,92,100,101,102,110,118,119,123))\n"
            ),
            # z/OS UNIX (OMVS) configuration.
            "BPXPRM00": (
                "ROOT FILESYSTEM('OMVS.GIBSON.ROOT.ZFS')\n"
                "     TYPE(ZFS) MODE(RDWR)\n"
                "MOUNT FILESYSTEM('OMVS.GIBSON.ETC.ZFS')\n"
                "      TYPE(ZFS) MODE(RDWR) MOUNTPOINT('/etc')\n"
                "MOUNT FILESYSTEM('OMVS.GIBSON.VAR.ZFS')\n"
                "      TYPE(ZFS) MODE(RDWR) MOUNTPOINT('/var')\n"
                "MOUNT FILESYSTEM('OMVS.GIBSON.TMP.ZFS')\n"
                "      TYPE(ZFS) MODE(RDWR) MOUNTPOINT('/tmp')\n"
                "MOUNT FILESYSTEM('OMVS.GIBSON.USERS.ZFS')\n"
                "      TYPE(ZFS) MODE(RDWR) MOUNTPOINT('/u')\n"
                "MAXPROCSYS(900)\n"
                "MAXPROCUSER(512)\n"
                "MAXUIDS(500)\n"
                "MAXFILEPROC(64000)\n"
                "MAXTHREADS(10000)\n"
                "MAXSOCKETS(64000)\n"
                "IPCMSGQBYTES(2147483647)\n"
                "FORKCOPY(COW)\n"
                "TTYGROUP(TTY)\n"
                "STARTUP_PROC(OMVS)\n"
                "NETWORK DOMAINNAME(AF_INET) DOMAINNUMBER(2)\n"
                "        MAXSOCKETS(64000) TYPE(INET)\n"
                "FILESYSTYPE TYPE(ZFS) ENTRYPOINT(IOEFSCM)\n"
                "FILESYSTYPE TYPE(INET) ENTRYPOINT(EZBPFINI)\n"
            ),
            # Allocation defaults.
            "ALLOC00": (
                "SPACE PRIMARY(2) SECONDARY(1) DIRECTORY(5)\n"
                "      MEASURE(TRK) PRIMARY_AUTOR(NO)\n"
                "SYSTEM IEFBR14_DELMIGDS(LEGACY)\n"
                "TIOT   SIZE(32)\n"
                "VOLENQ DELAY(2)\n"
            ),
            # Volume attributes (mount/use).
            "VATLST00": (
                "SBSYS1,1,0,SBSYS1\n"
                "SBRES1,1,0,SBRES1\n"
                "SBSMF1,0,0,SBSMF1\n"
                "SBWRK1,0,1,SBWRK1\n"
                "SBPAGE,0,0,SBPAGE\n"
            ),
            # GTF / diagnostics.
            "DIAG00": (
                "VSM TRACK CSA(ON) SQA(ON)\n"
                "VSM BESTFITCSA(YES)\n"
            ),
            # JES2 initialization deck (the HASPPARM the JES2 proc references).
            "JES2PARM": (
                "/*********************************************************************/\n"
                "/* SYS1.PARMLIB(JES2PARM) - JES2 initialization deck for member   */\n"
                "/* GIBSON. Single-member MAS, one DASD spool, NJE over TCP/IP.    */\n"
                "/*********************************************************************/\n"
                "/*------------------ Checkpoint definition ------------------------*/\n"
                "CKPTDEF CKPT1=(DSNAME=SYS1.GIBSON.CKPT1,VOLSER=SBCKP1,INUSE=YES),\n"
                "        CKPT2=(DSNAME=SYS1.GIBSON.CKPT2,VOLSER=SBCKP2,INUSE=YES),\n"
                "        NEWCKPT1=(DSNAME=SYS1.GIBSON.NEWCKPT1,VOLSER=SBCKP1),\n"
                "        NEWCKPT2=(DSNAME=SYS1.GIBSON.NEWCKPT2,VOLSER=SBCKP2),\n"
                "        MODE=DUPLEX,DUPLEX=ON,VERSIONS=(NUMBER=2),\n"
                "        LOGSIZE=4,OPVERIFY=NO\n"
                "/*------------------ Spool definition -----------------------------*/\n"
                "SPOOLDEF BUFSIZE=3992,\n"
                "        DSNAME=SYS1.HASPACE,\n"
                "        SPOOLNUM=32,\n"
                "        TGSIZE=30,\n"
                "        TGSPACE=(MAX=16288,WARN=80),\n"
                "        TRKCELL=3,\n"
                "        VOLUME=SBSPL\n"
                "/*------------------ Multi-access spool ---------------------------*/\n"
                "MASDEF  OWNMEMB=GIBSON,\n"
                "        AUTOEMEM=ON,\n"
                "        RESTART=YES,\n"
                "        SHARED=CHECK,\n"
                "        XCFGRPNM=GIBJES2,\n"
                "        DORMANCY=(0,100),\n"
                "        HOLD=99999\n"
                "/*------------------ Job/output number ranges ---------------------*/\n"
                "JOBDEF  JOBNUM=10000,\n"
                "        RANGE=(1,99999),\n"
                "        BAS_ACCT=NO,\n"
                "        ACCTFLD=OPTIONAL,\n"
                "        JNUMWARN=80\n"
                "OUTDEF  JOENUM=10000,JOEWARN=80,BUFWARN=80,\n"
                "        PRTYHIGH=14,PRTYLOW=2,PRTYRATE=0\n"
                "/*------------------ Job classes ----------------------------------*/\n"
                "JOBCLASS(A) ACCT=NO,AUTH=ALL,MSGCLASS=X,MSGLEVEL=(1,1),\n"
                "        OUTPUT=YES,REGION=0M,TIME=(30,0),SCHENV=,\n"
                "        PERFORM=0,PGMRNAME=OPTIONAL\n"
                "JOBCLASS(S) ACCT=NO,AUTH=ALL,MSGCLASS=X,REGION=0M,TIME=1440\n"
                "JOBCLASS(STC) AUTH=ALL,MSGCLASS=X,OUTPUT=YES,REGION=0M,TIME=1440\n"
                "JOBCLASS(TSU) AUTH=ALL,MSGCLASS=X,OUTPUT=YES,REGION=0M,TIME=1440\n"
                "STCCLASS MSGCLASS=X\n"
                "TSUCLASS MSGCLASS=X\n"
                "/*------------------ Output (SYSOUT) classes ----------------------*/\n"
                "OUTCLASS(A) OUTDISP=(WRITE,WRITE),OUTPUT=PRINT,TRKCELL=YES\n"
                "OUTCLASS(X) OUTDISP=(HOLD,HOLD),OUTPUT=PRINT\n"
                "OUTCLASS(Z) OUTDISP=(PURGE,PURGE)\n"
                "/*------------------ Estimates / limits ---------------------------*/\n"
                "ESTLNCT NUM=100000,INT=10000,OPT=0\n"
                "ESTBYTE NUM=2000000,INT=100000,OPT=0\n"
                "ESTPUN  NUM=100000,INT=10000,OPT=0\n"
                "ESTPAGE NUM=1000000,INT=100000,OPT=0\n"
                "/*------------------ Readers / printers / punch -------------------*/\n"
                "INTRDR  AUTH=(DEVICE=YES,JOB=YES,SYSTEM=YES),CLASS=A,RDINUM=20\n"
                "RDR(1)  CLASS=A\n"
                "PRINTDEF LINECT=60,CCWNUM=20,DBLBUFR=YES\n"
                "PRT(1)  CLASS=A,MODE=LINE,START=YES,ROUTECDE=LOCAL,SEP=YES,UCS=GIB1\n"
                "PUNCHDEF CCWNUM=10\n"
                "/*------------------ Initiators -----------------------------------*/\n"
                "INITDEF PARTNUM=20\n"
                "INIT(1) CLASS=ABS,NAME=INIT1,START=YES\n"
                "INIT(2) CLASS=ABS,NAME=INIT2,START=YES\n"
                "INIT(3) CLASS=SA,NAME=INIT3,START=YES\n"
                "/*------------------ Processor / TP / SMF / console ---------------*/\n"
                "PCEDEF  CNVTNUM=3,OUTNUM=3,PSONUM=2,PURGENUM=2,SPINNUM=3,STACNUM=2\n"
                "TPDEF   BSCBUF=(LIMIT=12),SNABUF=(LIMIT=12),SESSIONS=100,\n"
                "        RMTMSG=10,BUFSIZE=3840,EXTBUF=15\n"
                "SMFDEF  BUFNUM=4,BUFWARN=80\n"
                "CONDEF  CONSOLE=(MASTER),DISPLEN=60,BUFNUM=2000,BUFWARN=80,\n"
                "        CMDNUM=600,AUTOCMD=ENABLE\n"
                "/*------------------ NJE network ----------------------------------*/\n"
                "NJEDEF  OWNNODE=1,\n"
                "        NODENUM=10,\n"
                "        LINENUM=5,\n"
                "        MAILMSG=YES,\n"
                "        DELAY=120,\n"
                "        HDRBUF=(LIMIT=9,WARN=80),\n"
                "        JRNUM=2,JTNUM=2,SRNUM=2,STNUM=2,\n"
                "        RESTMAX=262136,RESTNODE=100,RESTTOL=0,\n"
                "        TIMETOL=1440\n"
                "NODE(1) NAME=GIBSON,DESCR='GIBSON TRAINING LPAR',\n"
                "        AUTH=(DEVICE=YES,JOB=YES,NET=YES,SYSTEM=YES)\n"
                "NODE(2) NAME=RYDELL,DESCR='PARTNER NODE RYDELL',\n"
                "        TRANSMIT=BOTH,RECEIVE=BOTH,PASSWORD=,\n"
                "        AUTH=(DEVICE=NO,JOB=NO,NET=NO,SYSTEM=NO)\n"
                "LINE(1) UNIT=TCP,JTRANS,JRECV,STRANS,SRECV\n"
                "NETSRV(1) SOCKET=LOCAL,STACK=TCPIP\n"
                "SOCKET(LOCAL) NODE=2,IPADDR=192.168.0.97,PORTNAME=VMNET,\n"
                "        SECURE=NO,CONNECT=YES\n"
                "APPL(GIBSON) NODE=1\n"
                "LOGON(1) APPLID=JES2\n"
                "/*------------------ Destinations / exits / load ------------------*/\n"
                "DESTID(LOCAL) DEST=LOCAL\n"
                "DESTID(RMT1)  DEST=R1\n"
                "/* LOADMOD(HASPXJCL) STORAGE=PVT */\n"
                "/* EXIT(0) ROUTINE=(GIBX000),STATUS=ENABLED */\n"
            ),
            # Storage Management Subsystem (SMS) - ACDS/COMMDS pair.
            "IGDSMS00": (
                "SMS ACDS(SYS1.SMS.GIBSON.ACDS)\n"
                "    COMMDS(SYS1.SMS.GIBSON.COMMDS)\n"
                "    INTERVAL(15)\n"
                "    DINTERVAL(150)\n"
                "    SMF_TIME(YES)\n"
                "    CACHETIME(3600)\n"
                "    DESELECT(MODULE)\n"
                "    REVERIFY(NO)\n"
                "    ACSDEFAULTS(NO)\n"
                "    SYSTEMS(8)\n"
                "    TRACE(ON) SIZE(128K) TYPE(ALL)\n"
                "    JOBNAME(*) ASID(*)\n"
                "    PDSE_RESTARTABLE_AS(YES)\n"
                "    PDSESHARING(NORMAL)\n"
            ),
            # Product enablement policy (which priced products are licensed/on).
            "IFAPRD00": (
                "PRODUCT OWNER('IBM CORP')\n"
                "        NAME('z/OS')\n"
                "        ID(5650-ZOS)\n"
                "        VERSION(*) RELEASE(*) MOD(*)\n"
                "        FEATURENAME('z/OS')\n"
                "        STATE(ENABLED)\n"
                "PRODUCT OWNER('IBM CORP')\n"
                "        NAME('z/OS')\n"
                "        ID(5650-ZOS)\n"
                "        VERSION(*) RELEASE(*) MOD(*)\n"
                "        FEATURENAME('RMF')\n"
                "        STATE(ENABLED)\n"
                "PRODUCT OWNER('IBM CORP')\n"
                "        NAME('z/OS')\n"
                "        ID(5650-ZOS)\n"
                "        VERSION(*) RELEASE(*) MOD(*)\n"
                "        FEATURENAME('SDSF')\n"
                "        STATE(ENABLED)\n"
                "PRODUCT OWNER('IBM CORP')\n"
                "        NAME('DB2 FOR Z/OS')\n"
                "        ID(5698-DB2)\n"
                "        VERSION(*) RELEASE(*) MOD(*)\n"
                "        FEATURENAME('DB2 FOR Z/OS')\n"
                "        STATE(ENABLED)\n"
                "PRODUCT OWNER('IBM CORP')\n"
                "        NAME('CICS TS FOR Z/OS')\n"
                "        ID(5655-Y04)\n"
                "        VERSION(*) RELEASE(*) MOD(*)\n"
                "        FEATURENAME('CICS TS')\n"
                "        STATE(ENABLED)\n"
            ),
        },
    },

    # ------------------------------------------------------------------ #
    #  SYS1.PROCLIB - started-task / logon procedures                    #
    # ------------------------------------------------------------------ #
    "SYS1.PROCLIB": {
        "ORG": "PO", "VOLUME": VOL_SYSRES, "refresh": True,
        "members": {
            # JES2 primary subsystem.
            "JES2": (
                "//JES2     PROC M=JES2PARM,N=00\n"
                "//IEFPROC  EXEC PGM=HASJES20,DPRTY=(15,15),\n"
                "//             TIME=1440,REGION=0M\n"
                "//PROC00   DD DSN=SYS1.PROCLIB,DISP=SHR\n"
                "//         DD DSN=CPAC.PROCLIB,DISP=SHR\n"
                "//HASPPARM DD DSN=SYS1.PARMLIB(&M),DISP=SHR\n"
                "//HASPLIST DD DDNAME=IEFRDER\n"
            ),
            # VTAM (SNA network).
            "NET": (
                "//NET      PROC LIST=00,BOOKMGR=,TFTP=,TCP=,IDLEN=15\n"
                "//VTAM     EXEC PGM=ISTINM01,REGION=0M,TIME=1440,\n"
                "//             DPRTY=(15,15)\n"
                "//VTAMLST  DD DSN=SYS1.VTAMLST,DISP=SHR\n"
                "//VTAMLIB  DD DSN=SYS1.VTAMLIB,DISP=SHR\n"
                "//ISTPDILG DD DSN=SYS1.PRDLG,DISP=SHR\n"
            ),
            # TCP/IP stack.
            "TCPIP": (
                "//TCPIP    PROC PARMS='CTRACE(CTIEZB00)',\n"
                "//             PROF=PROFILE,TCPDATA=TCPDATA\n"
                "//TCPIP    EXEC PGM=EZBTCPIP,REGION=0M,TIME=1440,\n"
                "//             PARM='&PARMS'\n"
                "//PROFILE  DD DSN=SYS1.TCPPARMS(&PROF),DISP=SHR\n"
                "//SYSTCPD  DD DSN=SYS1.TCPPARMS(&TCPDATA),DISP=SHR\n"
            ),
            # TN3270E Telnet server.
            "TN3270": (
                "//TN3270   PROC PROF=TN3270,TCPDATA=TCPDATA\n"
                "//TN3270   EXEC PGM=EZBTNINI,REGION=0M,TIME=1440,\n"
                "//             PARM='CTRACE(CTIEZBTN)'\n"
                "//PROFILE  DD DSN=SYS1.TCPPARMS(&PROF),DISP=SHR\n"
                "//SYSTCPD  DD DSN=SYS1.TCPPARMS(&TCPDATA),DISP=SHR\n"
            ),
            # z/OS UNIX kernel.
            "OMVS": (
                "//OMVS     PROC\n"
                "//OMVS     EXEC PGM=BPXINIT,REGION=0M,TIME=1440\n"
            ),
            # FTP server (started as FTPD1).
            "FTPD": (
                "//FTPD     PROC MODULE='FTPD',PARMS=''\n"
                "//FTPD     EXEC PGM=&MODULE,REGION=0M,TIME=1440,\n"
                "//             PARM='POSIX(ON) ALL31(ON)/&PARMS'\n"
                "//SYSTCPD  DD DSN=SYS1.TCPPARMS(TCPDATA),DISP=SHR\n"
                "//SYSFTPD  DD DSN=SYS1.TCPPARMS(FTPDATA),DISP=SHR\n"
            ),
            # TSO/VTAM terminal control (TCAS).
            "TSO": (
                "//TSO      PROC MEMBER=TSOKEY00\n"
                "//STEP1    EXEC PGM=IKTCAS00,TIME=1440\n"
                "//SYSTCPD  DD DSN=SYS1.TCPPARMS(TCPDATA),DISP=SHR\n"
            ),
            # TSO logon procedure used by users at LOGON.
            "TSOLOGON": (
                "//TSOLOGON PROC\n"
                "//IKJEFT01 EXEC PGM=IKJEFT01,DYNAMNBR=200,REGION=0M\n"
                "//SYSPROC  DD DSN=ISP.SISPCLIB,DISP=SHR\n"
                "//         DD DSN=SYS1.CLIST,DISP=SHR\n"
                "//SYSEXEC  DD DSN=SYS1.REXX,DISP=SHR\n"
                "//ISPPLIB  DD DSN=ISP.SISPPENU,DISP=SHR\n"
                "//ISPMLIB  DD DSN=ISP.SISPMENU,DISP=SHR\n"
                "//ISPSLIB  DD DSN=ISP.SISPSENU,DISP=SHR\n"
                "//ISPTLIB  DD DSN=ISP.SISPTENU,DISP=SHR\n"
                "//ISPPROF  DD DSN=&SYSUID..ISPF.PROFILE,DISP=SHR\n"
                "//SYSHELP  DD DSN=SYS1.HELP,DISP=SHR\n"
            ),
            # Library lookaside / VLF (run under MSTR).
            "LLA": (
                "//LLA      PROC LLA=00\n"
                "//LLA      EXEC PGM=CSVLLCRE,PARM='LLA=&LLA',TIME=1440\n"
                "//CSVLLAxx DD DSN=SYS1.PARMLIB,DISP=SHR\n"
            ),
            "VLF": (
                "//VLF      PROC NN=00\n"
                "//VLF      EXEC PGM=COFMINIT,PARM='NN=&NN',TIME=1440\n"
                "//COFVLFxx DD DSN=SYS1.PARMLIB,DISP=SHR\n"
            ),
            # RMF performance monitor.
            "RMF": (
                "//RMF      PROC IPARM=00\n"
                "//IEFPROC  EXEC PGM=ERBMFMFC,TIME=1440,DPRTY=(15,15),\n"
                "//             PARM='&IPARM'\n"
                "//MFMESSGE DD SYSOUT=A\n"
            ),
            # Db2 system address spaces.
            "DB2START": (
                "//DB2START PROC\n"
                "//DB2MSTR  EXEC PGM=DSN3MSTR,PARM='DB2D',REGION=0M,TIME=1440\n"
                "//BSDS01   DD DSN=DB2D.BSDS01,DISP=SHR\n"
                "//BSDS02   DD DSN=DB2D.BSDS02,DISP=SHR\n"
            ),
            "DB2MSTR": (
                "//DB2MSTR  PROC RGN=0M,PARM='DB2D'\n"
                "//IEFPROC  EXEC PGM=DSN3MSTR,REGION=&RGN,PARM=&PARM,TIME=1440\n"
                "//BSDS01   DD DSN=DB2D.BSDS01,DISP=SHR\n"
                "//BSDS02   DD DSN=DB2D.BSDS02,DISP=SHR\n"
            ),
            # CICS region.
            "CICSSTART": (
                "//CICSSTART PROC START=AUTO,SIP=00\n"
                "//CICS     EXEC PGM=DFHSIP,REGION=0M,TIME=1440,\n"
                "//             PARM='SI,START=&START,SYSIN'\n"
                "//STEPLIB  DD DSN=CICS.SDFHAUTH,DISP=SHR\n"
                "//DFHCSD   DD DSN=CICS.GIBSON.DFHCSD,DISP=SHR\n"
                "//SYSIN    DD DSN=CICS.SYSIN(DFH$SIP&SIP),DISP=SHR\n"
            ),
            # Initiator procedure.
            "INIT": (
                "//INIT     PROC\n"
                "//INIT     EXEC PGM=IEFIIC,DPRTY=(13,13)\n"
            ),
        },
    },

    # ------------------------------------------------------------------ #
    #  SYS1.VTAMLST - SNA network definitions                            #
    # ------------------------------------------------------------------ #
    "SYS1.VTAMLST": {
        "ORG": "PO", "VOLUME": VOL_SYSRES, "refresh": True,
        "members": {
            # VTAM start options.
            "ATCSTR00": (
                "SSCPID=01,\n"
                "SSCPNAME=GIBSSCP,\n"
                "NETID=GIBNET,\n"
                "HOSTSA=1,\n"
                "HOSTPU=GIBPU,\n"
                "NODETYPE=NN,\n"
                "DATEFORM=MDY,\n"
                "CONFIG=00,\n"
                "SUPP=NOSUP,\n"
                "NOPROMPT,\n"
                "MAXSUBA=255,\n"
                "IOINT=0,\n"
                "SGALIMIT=0,\n"
                "GREETING=YES,\n"
                "TNSTAT,CNSL,\n"
                "CSALIMIT=0,\n"
                "OSITOPO=ILUCDRSC,\n"
                "STRGR=ISTMNPS,\n"
                "STRMNPS=ISTMNPS\n"
            ),
            # Configuration list - major nodes activated at VTAM start.
            "ATCCON00": (
                "APPLTSO,\n"
                "APPLCICS,\n"
                "APPLTN,\n"
                "GIBLCL,\n"
                "GIBSWN,\n"
                "ISTLSXCF\n"
            ),
            # TSO application major node.
            "APPLTSO": (
                "TSOAPPL  VBUILD TYPE=APPL\n"
                "TSO00001 APPL   ACBNAME=TSO00001,AUTH=(PASS,TSO),\n"
                "               EAS=1,PARSESS=NO,SESSLIM=YES\n"
                "TSO00002 APPL   ACBNAME=TSO00002,AUTH=(PASS,TSO),\n"
                "               EAS=1,PARSESS=NO,SESSLIM=YES\n"
            ),
            # CICS application major node.
            "APPLCICS": (
                "CICSAPPL VBUILD TYPE=APPL\n"
                "CICSGIB1 APPL   ACBNAME=CICSGIB1,\n"
                "               AUTH=(ACQ,PASS,VPACE),\n"
                "               MODETAB=ISTINCLM,DLOGMOD=SNX32702,\n"
                "               PARSESS=YES,SONSCIP=YES,VPACING=10\n"
            ),
            # TN3270/Telnet APPL pool.
            "APPLTN": (
                "TNAPPL   VBUILD TYPE=APPL\n"
                "TCPABC01 APPL   AUTH=(PASS,NVPACE),EAS=10,\n"
                "               MODETAB=ISTINCLM,DLOGMOD=SNX32702,\n"
                "               PARSESS=YES,SESSLIM=NO\n"
            ),
            # Local non-SNA 3270 major node (locally attached terminals).
            "GIBLCL": (
                "GIBLCL   VBUILD TYPE=LOCAL\n"
                "LCL0700  LOCAL  CUADDR=0700,TERM=3277,\n"
                "               FEATUR2=(MODEL2,EDATS),\n"
                "               ISTATUS=ACTIVE,USSTAB=GIBUSS\n"
                "LCL0701  LOCAL  CUADDR=0701,TERM=3277,\n"
                "               FEATUR2=(MODEL2,EDATS),ISTATUS=ACTIVE\n"
            ),
            # Switched (dial / TN3270 LU) major node.
            "GIBSWN": (
                "GIBSWN   VBUILD TYPE=SWNET,MAXGRP=1,MAXNO=1\n"
                "SWPU01   PU     ADDR=01,IDBLK=05D,IDNUM=00001,\n"
                "               PUTYPE=2,MAXPATH=1,MAXDATA=265,\n"
                "               ISTATUS=ACTIVE\n"
                "SWLU01   LU     LOCADDR=2,DLOGMOD=SNX32702,\n"
                "               USSTAB=GIBUSS\n"
            ),
            # USS table reference (logon screen / commands).
            "GIBUSS": (
                "GIBUSS   USSTAB FORMAT=DYNAMIC\n"
                "         USSCMD CMD=LOGON,FORMAT=PL1\n"
                "         USSPARM PARM=APPLID\n"
                "         USSPARM PARM=LOGMODE\n"
                "         USSPARM PARM=DATA\n"
                "         USSCMD CMD=LOGOFF,FORMAT=PL1\n"
                "         USSEND\n"
            ),
        },
    },

    # ------------------------------------------------------------------ #
    #  SYS1.TCPPARMS - TCP/IP profile, resolver, FTP config              #
    # ------------------------------------------------------------------ #
    "SYS1.TCPPARMS": {
        "ORG": "PO", "VOLUME": VOL_SYSRES, "refresh": True,
        "members": {
            # The TCP/IP stack profile.
            "PROFILE": (
                "; TCP/IP PROFILE for stack TCPIP on system GIBSON\n"
                "ARPAGE 5\n"
                "GLOBALCONFIG NOTCPIPSTATISTICS\n"
                "IPCONFIG  DATAGRAMFWD SYSPLEXROUTING\n"
                "          DYNAMICXCF 10.1.1.1 255.255.255.0 1\n"
                "SOMAXCONN 10\n"
                "TCPCONFIG TCPSENDBFRSIZE 65535 TCPRCVBUFRSIZE 65535\n"
                "          SENDGARBAGE FALSE RESTRICTLOWPORTS\n"
                "UDPCONFIG RESTRICTLOWPORTS\n"
                ";\n"
                "DEVICE OSA1     MPCIPA\n"
                "LINK   ETH1     IPAQENET OSA1\n"
                ";\n"
                "HOME\n"
                "   192.168.0.96     ETH1\n"
                ";\n"
                "BEGINROUTES\n"
                "ROUTE 192.168.0.0  255.255.255.0 =          ETH1 MTU 1492\n"
                "ROUTE DEFAULT      192.168.0.1               ETH1 MTU 1492\n"
                "ENDROUTES\n"
                ";\n"
                "AUTOLOG 5\n"
                "   FTPD   JOBNAME FTPD1\n"
                "   TN3270\n"
                "ENDAUTOLOG\n"
                ";\n"
                "PORT\n"
                "    7 UDP MISC      ; Miscellaneous Server\n"
                "    7 TCP MISC      ; Miscellaneous Server\n"
                "   20 TCP FTPD1     ; FTP Server (data)\n"
                "   21 TCP FTPD1     ; FTP Server (control)\n"
                "   23 TCP TN3270    ; Telnet 3270 Server\n"
                "   25 TCP SMTP      ; SMTP Server\n"
                "   80 TCP OMVS      ; HTTP Server\n"
                "  111 TCP PORTMAP   ; SUN RPC Portmapper\n"
                "  175 TCP JES2      ; NJE over TCP/IP\n"
                "  443 TCP OMVS      ; HTTPS Server\n"
                "  512 TCP OMVS      ; remote execution\n"
                "  514 TCP OMVS      ; remote shell\n"
                " 2252 TCP JES2      ; NJE/TLS\n"
                "50000 TCP DB2DDF    ; Db2 DDF DRDA\n"
                ";\n"
                "SACONFIG ENABLED COMMUNITY public AGENT 161\n"
                "ITRACE OFF\n"
                "START OSA1\n"
            ),
            # Resolver / TCPIP.DATA.
            "TCPDATA": (
                "TCPIPJOBNAME     TCPIP\n"
                "HOSTNAME         GIBSON\n"
                "DOMAINORIGIN     GIBNET.LOCAL\n"
                "DATASETPREFIX    TCPIP\n"
                "NSINTERADDR      192.168.0.1\n"
                "NSPORTADDR       53\n"
                "RESOLVEVIA       UDP\n"
                "RESOLVERTIMEOUT  10\n"
                "RESOLVERUDPRETRIES 1\n"
                "LOOKUP           DNS LOCAL\n"
            ),
            # Resolver setup member (RESOLVER PROC points here).
            "RESOLVER": (
                "DEFAULTTCPIPDATA('SYS1.TCPPARMS(TCPDATA)')\n"
                "GLOBALTCPIPDATA('SYS1.TCPPARMS(TCPDATA)')\n"
                "DEFAULTIPNODES('SYS1.TCPPARMS(IPNODES)')\n"
                "COMMONSEARCH\n"
            ),
            # FTP server configuration.
            "FTPDATA": (
                "; FTP.DATA for the FTPD server\n"
                "BANNER          SYS1.TCPPARMS(FTPBANNR)\n"
                "ANONYMOUS\n"
                "ANONYMOUSLEVEL  3\n"
                "STARTDIRECTORY  HFS\n"
                "AUTOMOUNT       TRUE\n"
                "AUTORECALL      TRUE\n"
                "JESINTERFACELEVEL 2\n"
                "FILETYPE        SEQ\n"
                "SBDATACONN      (IBM-1047,ISO8859-1)\n"
                "CONDDISP        CATLG\n"
                "SQLCOL          NAMES\n"
                "DSWAITTIME      10\n"
                "INACTIVE        300\n"
                "PORTOFENTRY4    NETACCESS\n"
            ),
            # Static host table.
            "IPNODES": (
                "192.168.0.96    GIBSON GIBSON.GIBNET.LOCAL\n"
                "192.168.0.1     GATEWAY\n"
                "127.0.0.1       LOCALHOST\n"
            ),
        },
    },

    # ------------------------------------------------------------------ #
    #  Binary libraries - representative directory entries (object code) #
    #  Kept as create-if-missing (no refresh) so they don't clobber any  #
    #  runtime content; members are realistic names with a short note.   #
    # ------------------------------------------------------------------ #
    "SYS1.LINKLIB": {
        "ORG": "PO", "VOLUME": VOL_SYSRES,
        "members": {
            "IEFBR14": _LOADMOD, "IKJEFT01": _LOADMOD, "IDCAMS": _LOADMOD,
            "IEBCOPY": _LOADMOD, "IEBGENER": _LOADMOD, "ICKDSF": _LOADMOD,
            "SORT": _LOADMOD, "IEWL": _LOADMOD, "IEHLIST": _LOADMOD,
            "IEFIIC": _LOADMOD, "IEEMB860": _LOADMOD,
        },
    },
    "SYS1.LPALIB": {
        "ORG": "PO", "VOLUME": VOL_SYSRES,
        "members": {
            "IEAVINIT": _LOADMOD, "CSVLLA": _LOADMOD, "IGC0001C": _LOADMOD,
            "IEAVAR00": _LOADMOD, "ISTINCLM": _LOADMOD,
        },
    },
    "SYS1.MACLIB": {
        "ORG": "PO", "VOLUME": VOL_SYSRES,
        "members": {
            "DCB": _MACRO, "GETMAIN": _MACRO, "FREEMAIN": _MACRO,
            "WTO": _MACRO, "OPEN": _MACRO, "CLOSE": _MACRO, "GET": _MACRO,
            "PUT": _MACRO, "SAVE": _MACRO, "RETURN": _MACRO, "LINK": _MACRO,
            "IKJTSOEV": _MACRO, "ATTACH": _MACRO,
        },
    },
    "SYS1.SVCLIB": {
        "ORG": "PO", "VOLUME": VOL_SYSRES,
        "members": {"IEFSSN00": _LOADMOD, "IEAVESVC": _LOADMOD, "IGC0001I": _LOADMOD},
    },
    "SYS1.NUCLEUS": {
        "ORG": "PO", "VOLUME": VOL_SYSRES,
        "members": {"IEANUC01": _LOADMOD, "IEAVNP00": _LOADMOD, "IEAVNIP0": _LOADMOD},
    },

    # ------------------------------------------------------------------ #
    #  SYS1.HELP - TSO/E command help (text)                             #
    # ------------------------------------------------------------------ #
    "SYS1.HELP": {
        "ORG": "PO", "VOLUME": VOL_SYSRES, "refresh": True,
        "members": {
            "LISTUSER": (
                ")F FUNCTION -\n"
                "  THE LISTUSER COMMAND DISPLAYS INFORMATION ABOUT A RACF USER\n"
                "  PROFILE, INCLUDING GROUP CONNECTIONS AND SEGMENT DATA.\n"
                ")X SYNTAX -\n"
                "  LISTUSER  userid  [ TSO ] [ OMVS ] [ CICS ] [ NORACF ]\n"
            ),
            "LISTGRP": (
                ")F FUNCTION -\n"
                "  THE LISTGRP COMMAND DISPLAYS THE CONTENTS OF A RACF GROUP\n"
                "  PROFILE INCLUDING SUBGROUPS AND CONNECTED USERS.\n"
                ")X SYNTAX -\n"
                "  LISTGRP  group  [ OMVS ] [ NORACF ]\n"
            ),
        },
    },
}
