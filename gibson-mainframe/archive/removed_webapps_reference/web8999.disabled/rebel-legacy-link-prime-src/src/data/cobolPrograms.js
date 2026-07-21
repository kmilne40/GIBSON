export const COBOL_PROGRAMS = {
  CUST: {
    program_name: "CUSTMNT",
    transaction_code: "CUST",
    description: "Customer Maintenance Program",
    source_code: `       IDENTIFICATION DIVISION.
       PROGRAM-ID. CUSTMNT.
       AUTHOR. BANKING-SYSTEMS-GROUP.
       DATE-WRITTEN. 15/03/1984.
      *===============================================
      * CUSTOMER MAINTENANCE PROGRAM
      * HANDLES ADD/UPDATE/DELETE/INQUIRE ON
      * CUSTOMER MASTER TABLE
      *===============================================

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.

       01  WS-RESPONSE-CODE         PIC S9(8) COMP.
       01  WS-REASON-CODE           PIC S9(8) COMP.
       01  WS-CUSTOMER-ID           PIC X(8).
       01  WS-ACTION                PIC X(1).
           88  ACTION-ADD           VALUE 'A'.
           88  ACTION-UPDATE        VALUE 'U'.
           88  ACTION-DELETE        VALUE 'D'.
           88  ACTION-INQUIRE       VALUE 'I'.

       01  WS-CUSTOMER-RECORD.
           05  WS-CUST-ID           PIC X(8).
           05  WS-SURNAME           PIC X(30).
           05  WS-FORENAME          PIC X(20).
           05  WS-DOB               PIC X(8).
           05  WS-SORT-CODE         PIC X(6).
           05  WS-NI-NUMBER         PIC X(9).
           05  WS-ADDRESS1          PIC X(30).
           05  WS-ADDRESS2          PIC X(30).
           05  WS-ADDRESS3          PIC X(30).
           05  WS-POSTCODE          PIC X(8).
           05  WS-STATUS            PIC X(1).
           05  WS-CUST-TYPE         PIC X(1).
           05  WS-OPEN-DATE         PIC X(8).
           05  WS-OPERATOR-ID       PIC X(8).
           05  WS-LAST-UPD-DATE     PIC X(8).

       COPY DFHCOMMAREA.
       COPY CUSTMAP.

       PROCEDURE DIVISION.

       MAIN-LOGIC.
           EVALUATE TRUE
               WHEN ACTION-ADD
                   PERFORM ADD-CUSTOMER
               WHEN ACTION-UPDATE
                   PERFORM UPDATE-CUSTOMER
               WHEN ACTION-DELETE
                   PERFORM DELETE-CUSTOMER
               WHEN ACTION-INQUIRE
                   PERFORM INQUIRE-CUSTOMER
               WHEN OTHER
                   MOVE 'PGMIDERR' TO WS-CICS-RESP
                   PERFORM SEND-ERROR-MAP
           END-EVALUATE
           EXEC CICS RETURN
               TRANSID('CUST')
               COMMAREA(DFHCOMMAREA)
           END-EXEC.

       ADD-CUSTOMER.
           EXEC CICS WRITE
               FILE('CUSTMAST')
               FROM(WS-CUSTOMER-RECORD)
               RIDFLD(WS-CUST-ID)
               RESP(WS-RESPONSE-CODE)
               RESP2(WS-REASON-CODE)
           END-EXEC
           EVALUATE WS-RESPONSE-CODE
               WHEN DFHRESP(NORMAL)
                   MOVE 'CUSTOMER ADDED SUCCESSFULLY' TO WS-MSG
               WHEN DFHRESP(DUPREC)
                   MOVE 'DUPKEY - CUSTOMER ID EXISTS' TO WS-MSG
               WHEN OTHER
                   MOVE 'ERROR WRITING CUSTOMER RECORD' TO WS-MSG
           END-EVALUATE.

       INQUIRE-CUSTOMER.
           EXEC CICS READ
               FILE('CUSTMAST')
               INTO(WS-CUSTOMER-RECORD)
               RIDFLD(WS-CUST-ID)
               RESP(WS-RESPONSE-CODE)
           END-EXEC
           EVALUATE WS-RESPONSE-CODE
               WHEN DFHRESP(NORMAL)
                   PERFORM POPULATE-MAP
               WHEN DFHRESP(NOTFND)
                   MOVE 'NOTFND - CUSTOMER NOT ON FILE' TO WS-MSG
               WHEN OTHER
                   MOVE 'ERROR READING CUSTOMER RECORD' TO WS-MSG
           END-EVALUATE.

       UPDATE-CUSTOMER.
           EXEC CICS REWRITE
               FILE('CUSTMAST')
               FROM(WS-CUSTOMER-RECORD)
               RESP(WS-RESPONSE-CODE)
           END-EXEC.

       DELETE-CUSTOMER.
           MOVE 'D' TO WS-STATUS
           EXEC CICS REWRITE
               FILE('CUSTMAST')
               FROM(WS-CUSTOMER-RECORD)
               RESP(WS-RESPONSE-CODE)
           END-EXEC.

       POPULATE-MAP.
           MOVE WS-SURNAME    TO CUSTMAPO-SURNAME
           MOVE WS-FORENAME   TO CUSTMAPO-FORENAME
           MOVE WS-DOB        TO CUSTMAPO-DOB
           MOVE WS-SORT-CODE  TO CUSTMAPO-SORT-CODE
           MOVE WS-ADDRESS1   TO CUSTMAPO-ADDR1
           MOVE WS-STATUS     TO CUSTMAPO-STATUS.`,
    sql_ddl: `-- ================================================
-- DB2 TABLE DEFINITION: CUSTOMER MASTER
-- DATABASE: BANKDB01
-- TABLESPACE: CUSTTS
-- ================================================

CREATE TABLE BANKDB01.CUSTOMER
  (CUSTOMER_ID      CHAR(8)      NOT NULL,
   SURNAME          CHAR(30)     NOT NULL,
   FORENAME         CHAR(20)     NOT NULL,
   DOB              CHAR(8),
   SORT_CODE        CHAR(6),
   NI_NUMBER        CHAR(9),
   ADDRESS1         CHAR(30),
   ADDRESS2         CHAR(30),
   ADDRESS3         CHAR(30),
   POSTCODE         CHAR(8),
   STATUS           CHAR(1)      NOT NULL DEFAULT 'A',
   CUSTOMER_TYPE    CHAR(1)      NOT NULL DEFAULT 'P',
   OPEN_DATE        CHAR(8),
   OPERATOR_ID      CHAR(8),
   LAST_UPD_DATE    CHAR(8),
   CONSTRAINT PK_CUSTOMER
     PRIMARY KEY (CUSTOMER_ID),
   CONSTRAINT CHK_STATUS
     CHECK (STATUS IN ('A','I','D')),
   CONSTRAINT CHK_CTYPE
     CHECK (CUSTOMER_TYPE IN ('P','C'))
  )
  IN BANKDB01.CUSTTS;

CREATE UNIQUE INDEX BANKDB01.XCUST01
  ON BANKDB01.CUSTOMER (CUSTOMER_ID ASC);

CREATE INDEX BANKDB01.XCUST02
  ON BANKDB01.CUSTOMER (SURNAME ASC, FORENAME ASC);

GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE BANKDB01.CUSTOMER
  TO ROLE BANK_APP_ROLE;

-- ================================================
-- RUNTIME SQL - INQUIRE (PF8)
-- ================================================
SELECT CUSTOMER_ID, SURNAME, FORENAME, DOB,
       SORT_CODE, NI_NUMBER, ADDRESS1, ADDRESS2,
       ADDRESS3, POSTCODE, STATUS, CUSTOMER_TYPE,
       OPEN_DATE, OPERATOR_ID, LAST_UPD_DATE
  FROM BANKDB01.CUSTOMER
 WHERE CUSTOMER_ID = :WS-CUST-ID;

-- ================================================
-- RUNTIME SQL - ADD (PF5)
-- ================================================
INSERT INTO BANKDB01.CUSTOMER
  (CUSTOMER_ID, SURNAME, FORENAME, DOB, SORT_CODE,
   NI_NUMBER, ADDRESS1, ADDRESS2, ADDRESS3, POSTCODE,
   STATUS, CUSTOMER_TYPE, OPEN_DATE, OPERATOR_ID,
   LAST_UPD_DATE)
VALUES
  (:WS-CUST-ID, :WS-SURNAME, :WS-FORENAME, :WS-DOB,
   :WS-SORT-CODE, :WS-NI-NUMBER, :WS-ADDR1, :WS-ADDR2,
   :WS-ADDR3, :WS-POSTCODE, :WS-STATUS, :WS-CUST-TYPE,
   :WS-OPEN-DATE, :WS-OPERATOR, :WS-LAST-UPD);

-- ================================================
-- RUNTIME SQL - UPDATE (PF6)
-- ================================================
UPDATE BANKDB01.CUSTOMER
   SET SURNAME       = :WS-SURNAME,
       FORENAME      = :WS-FORENAME,
       ADDRESS1      = :WS-ADDR1,
       ADDRESS2      = :WS-ADDR2,
       POSTCODE      = :WS-POSTCODE,
       STATUS        = :WS-STATUS,
       LAST_UPD_DATE = :WS-TODAY,
       OPERATOR_ID   = :WS-OPERATOR
 WHERE CUSTOMER_ID   = :WS-CUST-ID;`
  },

  ACCT: {
    program_name: "ACCTMNT",
    transaction_code: "ACCT",
    description: "Account Maintenance Program",
    source_code: `       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTMNT.
       AUTHOR. BANKING-SYSTEMS-GROUP.
       DATE-WRITTEN. 22/06/1984.
      *===============================================
      * ACCOUNT MAINTENANCE PROGRAM
      * HANDLES OPEN/MODIFY/INQUIRE ON ACCOUNT TABLE
      *===============================================

       DATA DIVISION.
       WORKING-STORAGE SECTION.

       01  WS-RESPONSE-CODE         PIC S9(8) COMP.
       01  WS-ACCOUNT-NUMBER        PIC X(10).
       01  WS-CUSTOMER-ID           PIC X(8).

       01  WS-ACCOUNT-RECORD.
           05  WS-ACCT-NUM          PIC X(10).
           05  WS-CUST-ID           PIC X(8).
           05  WS-ACCT-TYPE         PIC X(3).
           05  WS-SORT-CODE         PIC X(6).
           05  WS-OPEN-DATE         PIC X(8).
           05  WS-CURRENCY          PIC X(3).
           05  WS-BALANCE           PIC S9(11)V99 COMP-3.
           05  WS-CREDIT-LIMIT      PIC S9(11)V99 COMP-3.
           05  WS-INTEREST-RATE     PIC 9(3)V99 COMP-3.
           05  WS-STATUS            PIC X(1).
           05  WS-OPERATOR-ID       PIC X(8).
           05  WS-LAST-UPD-DATE     PIC X(8).

       COPY DFHCOMMAREA.
       COPY ACCTMAP.

       PROCEDURE DIVISION.

       MAIN-LOGIC.
           EVALUATE EIBAID
               WHEN DFHPF5
                   PERFORM OPEN-ACCOUNT
               WHEN DFHPF6
                   PERFORM MODIFY-ACCOUNT
               WHEN DFHPF8
                   PERFORM INQUIRE-ACCOUNT
               WHEN DFHPF9
                   PERFORM NEXT-ACCOUNT
               WHEN DFHENTER
                   PERFORM SEND-ACCT-MAP
               WHEN OTHER
                   PERFORM SEND-ACCT-MAP
           END-EVALUATE
           EXEC CICS RETURN
               TRANSID('ACCT')
               COMMAREA(DFHCOMMAREA)
           END-EXEC.

       OPEN-ACCOUNT.
           EXEC CICS WRITE
               FILE('ACCTMAST')
               FROM(WS-ACCOUNT-RECORD)
               RIDFLD(WS-ACCT-NUM)
               RESP(WS-RESPONSE-CODE)
           END-EXEC
           IF WS-RESPONSE-CODE = DFHRESP(NORMAL)
               MOVE 'ACCOUNT OPENED SUCCESSFULLY' TO WS-MSG
           ELSE IF WS-RESPONSE-CODE = DFHRESP(DUPREC)
               MOVE 'DUPKEY - ACCOUNT NUMBER EXISTS' TO WS-MSG
           END-IF.

       INQUIRE-ACCOUNT.
           EXEC CICS READ
               FILE('ACCTMAST')
               INTO(WS-ACCOUNT-RECORD)
               RIDFLD(WS-ACCT-NUM)
               RESP(WS-RESPONSE-CODE)
           END-EXEC
           IF WS-RESPONSE-CODE = DFHRESP(NORMAL)
               PERFORM POPULATE-ACCT-MAP
           ELSE
               MOVE 'NOTFND - ACCOUNT NOT ON FILE' TO WS-MSG
           END-IF.

       MODIFY-ACCOUNT.
           EXEC CICS READ
               FILE('ACCTMAST')
               INTO(WS-ACCOUNT-RECORD)
               RIDFLD(WS-ACCT-NUM)
               UPDATE
               RESP(WS-RESPONSE-CODE)
           END-EXEC
           PERFORM APPLY-UPDATES
           EXEC CICS REWRITE
               FILE('ACCTMAST')
               FROM(WS-ACCOUNT-RECORD)
               RESP(WS-RESPONSE-CODE)
           END-EXEC.

       NEXT-ACCOUNT.
           EXEC CICS READNEXT
               FILE('ACCTMAST')
               INTO(WS-ACCOUNT-RECORD)
               RIDFLD(WS-ACCT-NUM)
               RESP(WS-RESPONSE-CODE)
           END-EXEC.`,
    sql_ddl: `-- ================================================
-- DB2 TABLE DEFINITION: ACCOUNT MASTER
-- DATABASE: BANKDB01
-- TABLESPACE: ACCTTS
-- ================================================

CREATE TABLE BANKDB01.ACCOUNT
  (ACCOUNT_NUMBER   CHAR(10)     NOT NULL,
   CUSTOMER_ID      CHAR(8)      NOT NULL,
   ACCOUNT_TYPE     CHAR(3)      NOT NULL,
   SORT_CODE        CHAR(6),
   OPEN_DATE        CHAR(8),
   CURRENCY         CHAR(3)      NOT NULL DEFAULT 'GBP',
   BALANCE          DECIMAL(13,2) NOT NULL DEFAULT 0,
   CREDIT_LIMIT     DECIMAL(13,2) NOT NULL DEFAULT 0,
   INTEREST_RATE    DECIMAL(5,2)  NOT NULL DEFAULT 0,
   STATUS           CHAR(1)      NOT NULL DEFAULT 'A',
   OPERATOR_ID      CHAR(8),
   LAST_UPD_DATE    CHAR(8),
   CONSTRAINT PK_ACCOUNT
     PRIMARY KEY (ACCOUNT_NUMBER),
   CONSTRAINT FK_ACCT_CUST
     FOREIGN KEY (CUSTOMER_ID)
     REFERENCES BANKDB01.CUSTOMER (CUSTOMER_ID),
   CONSTRAINT CHK_ACCT_TYPE
     CHECK (ACCOUNT_TYPE IN ('SAV','CUR','OVD','LON')),
   CONSTRAINT CHK_ACCT_STATUS
     CHECK (STATUS IN ('A','D','F'))
  )
  IN BANKDB01.ACCTTS;

CREATE UNIQUE INDEX BANKDB01.XACCT01
  ON BANKDB01.ACCOUNT (ACCOUNT_NUMBER ASC);

CREATE INDEX BANKDB01.XACCT02
  ON BANKDB01.ACCOUNT (CUSTOMER_ID ASC, ACCOUNT_NUMBER ASC);

-- ================================================
-- RUNTIME SQL - INQUIRE (PF8)
-- ================================================
SELECT ACCOUNT_NUMBER, CUSTOMER_ID, ACCOUNT_TYPE,
       SORT_CODE, OPEN_DATE, CURRENCY, BALANCE,
       CREDIT_LIMIT, INTEREST_RATE, STATUS,
       OPERATOR_ID, LAST_UPD_DATE
  FROM BANKDB01.ACCOUNT
 WHERE ACCOUNT_NUMBER = :WS-ACCT-NUM;

-- ================================================
-- RUNTIME SQL - OPEN ACCOUNT (PF5)
-- ================================================
INSERT INTO BANKDB01.ACCOUNT
  (ACCOUNT_NUMBER, CUSTOMER_ID, ACCOUNT_TYPE,
   SORT_CODE, OPEN_DATE, CURRENCY, BALANCE,
   CREDIT_LIMIT, INTEREST_RATE, STATUS,
   OPERATOR_ID, LAST_UPD_DATE)
VALUES
  (:WS-ACCT-NUM, :WS-CUST-ID, :WS-ACCT-TYPE,
   :WS-SORT-CODE, :WS-TODAY, :WS-CURRENCY, 0,
   :WS-CREDIT-LIM, :WS-INT-RATE, 'A',
   :WS-OPERATOR, :WS-TODAY);

-- ================================================
-- RUNTIME SQL - LIST ACCOUNTS FOR CUSTOMER
-- ================================================
SELECT ACCOUNT_NUMBER, ACCOUNT_TYPE, BALANCE,
       STATUS, CURRENCY
  FROM BANKDB01.ACCOUNT
 WHERE CUSTOMER_ID = :WS-CUST-ID
 ORDER BY ACCOUNT_NUMBER ASC;`
  },

  TRAN: {
    program_name: "TRANPST",
    transaction_code: "TRAN",
    description: "Transaction Posting Program",
    source_code: `       IDENTIFICATION DIVISION.
       PROGRAM-ID. TRANPST.
       AUTHOR. BANKING-SYSTEMS-GROUP.
       DATE-WRITTEN. 10/09/1984.
      *===============================================
      * TRANSACTION POSTING PROGRAM
      * POSTS DEBITS, CREDITS, AND TRANSFERS
      * UPDATES ACCOUNT BALANCE AFTER EACH POSTING
      *===============================================

       DATA DIVISION.
       WORKING-STORAGE SECTION.

       01  WS-RESPONSE-CODE         PIC S9(8) COMP.
       01  WS-ACCOUNT-NUMBER        PIC X(10).
       01  WS-TO-ACCOUNT            PIC X(10).
       01  WS-TRAN-TYPE             PIC X(3).
       01  WS-AMOUNT                PIC S9(11)V99 COMP-3.
       01  WS-NEW-BALANCE           PIC S9(11)V99 COMP-3.
       01  WS-OLD-BALANCE           PIC S9(11)V99 COMP-3.
       01  WS-TRAN-ID               PIC X(12).

       01  WS-TRAN-RECORD.
           05  WS-TRAN-ID-F         PIC X(12).
           05  WS-ACCT-NUM          PIC X(10).
           05  WS-TRAN-TYPE-F       PIC X(3).
           05  WS-AMOUNT-F          PIC S9(11)V99 COMP-3.
           05  WS-DESCRIPTION       PIC X(40).
           05  WS-REFERENCE         PIC X(12).
           05  WS-TO-ACCT           PIC X(10).
           05  WS-VALUE-DATE        PIC X(8).
           05  WS-POST-DATE         PIC X(8).
           05  WS-POST-TIME         PIC X(6).
           05  WS-BAL-AFTER         PIC S9(11)V99 COMP-3.
           05  WS-OPERATOR          PIC X(8).

       01  WS-ACCOUNT-RECORD.
           05  WS-ACCT-NUM-2        PIC X(10).
           05  WS-BALANCE           PIC S9(11)V99 COMP-3.
           05  WS-CREDIT-LIMIT      PIC S9(11)V99 COMP-3.
           05  WS-ACCT-STATUS       PIC X(1).

       COPY DFHCOMMAREA.
       COPY TRANMAP.

       PROCEDURE DIVISION.

       MAIN-LOGIC.
           EVALUATE EIBAID
               WHEN DFHPF5
                   PERFORM POST-TRANSACTION
               WHEN DFHPF8
                   PERFORM VIEW-HISTORY
               WHEN DFHENTER
                   PERFORM SEND-TRAN-MAP
               WHEN OTHER
                   PERFORM SEND-TRAN-MAP
           END-EVALUATE
           EXEC CICS RETURN
               TRANSID('TRAN')
               COMMAREA(DFHCOMMAREA)
           END-EXEC.

       POST-TRANSACTION.
           PERFORM VALIDATE-INPUT
           PERFORM READ-ACCOUNT-FOR-UPDATE
           IF VALID-TRANSACTION
               PERFORM CALCULATE-NEW-BALANCE
               PERFORM CHECK-CREDIT-LIMIT
               PERFORM WRITE-TRANSACTION
               PERFORM UPDATE-ACCOUNT-BALANCE
               IF WS-TRAN-TYPE = 'TRF'
                   PERFORM POST-TRANSFER-CREDIT
               END-IF
               MOVE 'TRANSACTION POSTED SUCCESSFULLY' TO WS-MSG
           END-IF.

       READ-ACCOUNT-FOR-UPDATE.
           EXEC CICS READ
               FILE('ACCTMAST')
               INTO(WS-ACCOUNT-RECORD)
               RIDFLD(WS-ACCOUNT-NUMBER)
               UPDATE
               RESP(WS-RESPONSE-CODE)
           END-EXEC
           IF WS-RESPONSE-CODE NOT = DFHRESP(NORMAL)
               MOVE 'NOTFND - ACCOUNT NOT ON FILE' TO WS-MSG
               SET INVALID-TRANSACTION TO TRUE
           END-IF.

       CALCULATE-NEW-BALANCE.
           MOVE WS-BALANCE TO WS-OLD-BALANCE
           EVALUATE WS-TRAN-TYPE
               WHEN 'CR'
                   COMPUTE WS-NEW-BALANCE =
                       WS-OLD-BALANCE + WS-AMOUNT
               WHEN 'DR'
                   COMPUTE WS-NEW-BALANCE =
                       WS-OLD-BALANCE - WS-AMOUNT
               WHEN 'TRF'
                   COMPUTE WS-NEW-BALANCE =
                       WS-OLD-BALANCE - WS-AMOUNT
           END-EVALUATE.

       WRITE-TRANSACTION.
           EXEC CICS WRITE
               FILE('TRANLOG')
               FROM(WS-TRAN-RECORD)
               RIDFLD(WS-TRAN-ID-F)
               RESP(WS-RESPONSE-CODE)
           END-EXEC.

       UPDATE-ACCOUNT-BALANCE.
           MOVE WS-NEW-BALANCE TO WS-BALANCE
           EXEC CICS REWRITE
               FILE('ACCTMAST')
               FROM(WS-ACCOUNT-RECORD)
               RESP(WS-RESPONSE-CODE)
           END-EXEC.`,
    sql_ddl: `-- ================================================
-- DB2 TABLE DEFINITION: TRANSACTION LOG
-- DATABASE: BANKDB01
-- TABLESPACE: TRANLTS
-- ================================================

CREATE TABLE BANKDB01.TRANLOG
  (TRAN_ID          CHAR(12)     NOT NULL,
   ACCOUNT_NUMBER   CHAR(10)     NOT NULL,
   TRAN_TYPE        CHAR(3)      NOT NULL,
   AMOUNT           DECIMAL(13,2) NOT NULL,
   DESCRIPTION      CHAR(40),
   REFERENCE        CHAR(12),
   TO_ACCOUNT       CHAR(10),
   VALUE_DATE       CHAR(8),
   POST_DATE        CHAR(8)      NOT NULL,
   POST_TIME        CHAR(6)      NOT NULL,
   BALANCE_AFTER    DECIMAL(13,2) NOT NULL,
   OPERATOR_ID      CHAR(8),
   CONSTRAINT PK_TRANLOG
     PRIMARY KEY (TRAN_ID),
   CONSTRAINT FK_TRAN_ACCT
     FOREIGN KEY (ACCOUNT_NUMBER)
     REFERENCES BANKDB01.ACCOUNT (ACCOUNT_NUMBER),
   CONSTRAINT CHK_TRAN_TYPE
     CHECK (TRAN_TYPE IN ('CR','DR','TRF'))
  )
  IN BANKDB01.TRANLTS;

CREATE INDEX BANKDB01.XTRAN01
  ON BANKDB01.TRANLOG (ACCOUNT_NUMBER ASC, POST_DATE DESC);

CREATE INDEX BANKDB01.XTRAN02
  ON BANKDB01.TRANLOG (POST_DATE DESC, POST_TIME DESC);

-- ================================================
-- RUNTIME SQL - POST TRANSACTION (PF5)
-- ================================================
INSERT INTO BANKDB01.TRANLOG
  (TRAN_ID, ACCOUNT_NUMBER, TRAN_TYPE, AMOUNT,
   DESCRIPTION, REFERENCE, TO_ACCOUNT, VALUE_DATE,
   POST_DATE, POST_TIME, BALANCE_AFTER, OPERATOR_ID)
VALUES
  (:WS-TRAN-ID, :WS-ACCT-NUM, :WS-TRAN-TYPE,
   :WS-AMOUNT, :WS-DESCRIPTION, :WS-REFERENCE,
   :WS-TO-ACCT, :WS-VALUE-DATE, :WS-TODAY,
   :WS-TIME-NOW, :WS-NEW-BAL, :WS-OPERATOR);

-- ================================================
-- RUNTIME SQL - UPDATE BALANCE AFTER POSTING
-- ================================================
UPDATE BANKDB01.ACCOUNT
   SET BALANCE       = :WS-NEW-BALANCE,
       LAST_UPD_DATE = :WS-TODAY,
       OPERATOR_ID   = :WS-OPERATOR
 WHERE ACCOUNT_NUMBER = :WS-ACCT-NUM;

-- ================================================
-- RUNTIME SQL - VIEW HISTORY (PF8)
-- ================================================
SELECT TRAN_ID, POST_DATE, POST_TIME, TRAN_TYPE,
       AMOUNT, BALANCE_AFTER, REFERENCE, DESCRIPTION
  FROM BANKDB01.TRANLOG
 WHERE ACCOUNT_NUMBER = :WS-ACCT-NUM
 ORDER BY POST_DATE DESC, POST_TIME DESC
 FETCH FIRST 100 ROWS ONLY;`
  }
};