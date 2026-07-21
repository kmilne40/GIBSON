       IDENTIFICATION DIVISION.
       PROGRAM-ID. VULNERABLE-BANK-UPDATE.
       AUTHOR. SECURITY-TRAINER.
       REMARKS. THIS PROGRAM CONTAINS INTENTIONAL VULNERABILITIES FOR TRAINING.

      *===============================================================*
      *                MULTIPLE INTENTIONAL VULNERABILITIES            *
      *===============================================================*

       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.

      *=================== UNSAFE DATA STRUCTURES ====================*
      * Vulnerability 1: Buffer overflow potential due to mismatched sizes
       01  INPUT-DATA.
           05  USER-INPUT               PIC X(100).  *> Large input buffer
           05  FILLER REDEFINES USER-INPUT.
               10  CUSTOMER-ID         PIC X(10).
               10  ACCOUNT-TYPE        PIC X(2).
               10  TRANSACTION-AMOUNT  PIC X(12).

      * Vulnerability 2: Sensitive data adjacent to overflowable buffers
       01  SECURITY-CONTROL-FLAGS.
           05  AUTHENTICATED-FLAG      PIC X VALUE 'N'.
           05  ADMIN-FLAG              PIC X VALUE 'N'.
           05  DEBUG-FLAG              PIC X VALUE 'N'.

      * Vulnerability 3: Fixed-size buffer for variable-length data
       01  CUSTOMER-RECORD.
           05  CUST-NAME               PIC X(30).
           05  CUST-ADDRESS            PIC X(50).
           05  CUST-BALANCE            PIC S9(9)V99 COMP-3.
           05  CUST-PIN                PIC X(4).  *> Easily overflowable

      * Vulnerability 4: Uninitialized sensitive data
       01  TEMP-STORAGE.
           05  SENSITIVE-TEMP          PIC X(100).
           05  LOG-BUFFER              PIC X(256).

      * Vulnerability 5: Format string in message buffer
       01  MESSAGE-AREA.
           05  MSG-TEXT                PIC X(100).
           05  MSG-SEVERITY            PIC X(1).

       LINKAGE SECTION.
      * Vulnerability 6: Exposed system control area
       01  DFHCOMMAREA.
           05  SYSTEM-CONTROL          PIC X(50).

       PROCEDURE DIVISION.

      *=================== VULNERABLE CODE SECTIONS ==================*
      * Vulnerability 15: Unsafe CICS channel communication
       500-GET-CHANNEL-DATA.
           EXEC CICS GET CONTAINER('USERDATA')
                         CHANNEL('BANKCHAN')
                         INTO(USER-INPUT)
                         FLENGTH(USER-INPUT-LENGTH) *> No MAXFLENGTH!
                         RESP(RESPONSE-CODE)
           END-EXEC.
           
           IF RESPONSE-CODE = DFHRESP(NORMAL)
               MOVE USER-INPUT TO CUSTOMER-RECORD. *> Potential overflow
           END-IF.
           
      * Vulnerability 7: Unsafe input handling with no length validation
       100-GET-INPUT.
           EXEC CICS RECEIVE MAP('BANKMAP') INTO(USER-INPUT) END-EXEC.

      * Vulnerability 8: Direct move with potential overflow
           MOVE USER-INPUT TO CUSTOMER-RECORD.

      * Vulnerability 9: Format string vulnerability in message
           STRING 'Tx for: ' CUST-NAME ' Amt: ' TRANSACTION-AMOUNT INTO MSG-TEXT.

      * Vulnerability 10: Authentication bypass via buffer overflow
           IF CUST-PIN = '9999' OR AUTHENTICATED-FLAG = 'Y'
               PERFORM 200-PROCESS-TRANSACTION
           ELSE
               PERFORM 800-SEND-ERROR
           END-IF.

      * Vulnerability 11: Debug backdoor via overflow
           IF DEBUG-FLAG = 'Y'
               PERFORM 700-DEBG-DUMP
           END-IF.

       200-PROCESS-TRANSACTION.
      * Vulnerability 12: Unsafe numeric conversion
           COMPUTE CUST-BALANCE = FUNCTION NUMVAL(TRANSACTION-AMOUNT).
      * Vulnerability 13: Logging sensitive data without sanitization
           MOVE CUSTOMER-RECORD TO LOG-BUFFER.
           EXEC CICS SEND MAP('BANKMAP') FROM(MESSAGE-AREA) END-EXEC.

       700-DEBG-DUMP.
      * Vulnerability 14: Exposing memory contents
           DISPLAY 'DEBUG DUMP: ' TEMP-STORAGE.

       800-SEND-ERROR.
           MOVE 'AUTHENTICATION FAILED' TO MSG-TEXT.
           EXEC CICS SEND MAP('BANKMAP') FROM(MESSAGE-AREA) END-EXEC.
