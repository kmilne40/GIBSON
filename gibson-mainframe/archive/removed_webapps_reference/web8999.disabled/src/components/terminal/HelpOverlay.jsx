import React from 'react';

const HELP_CONTENT = {
  MENU: {
    title: 'BKGMENU - MAIN MENU HELP',
    lines: [
      'BANKMASTER/VS  -  MAIN TRANSACTION MENU',
      '',
      'TO SELECT A TRANSACTION, TYPE THE NUMBER OR CODE AND PRESS ENTER.',
      '',
      '  1  CUST  -  CUSTOMER MASTER MAINTENANCE',
      '             ADD, MODIFY, DELETE, INQUIRE CUSTOMER RECORDS.',
      '             FIELDS: CUSTOMER-ID, NAME, DOB, NI NUMBER,',
      '             ADDRESS, STATUS (A=ACTIVE I=INACTIVE D=DELETED)',
      '',
      '  2  ACCT  -  ACCOUNT MAINTENANCE & BALANCE INQUIRY',
      '             OPEN ACCOUNTS, VIEW BALANCES, MODIFY TERMS.',
      '             TYPES: SAV=SAVINGS  CUR=CURRENT  OVD=OVERDRAFT',
      '                    LON=LOAN',
      '',
      '  3  TRAN  -  TRANSACTION POSTING',
      '             POST DEBITS, CREDITS, AND TRANSFERS.',
      '             TYPES: CR=CREDIT  DR=DEBIT  TRF=TRANSFER',
      '',
      '  5  LOGO  -  SIGN OFF TERMINAL',
      '',
      'PF KEY SUMMARY:',
      '  PF1  = CONTEXT HELP (THIS SCREEN)',
      '  PF3  = RETURN / CANCEL / SIGN OFF',
      '  PF5  = ADD / OPEN / POST',
      '  PF6  = UPDATE / MODIFY',
      '  PF7  = SCROLL UP / PREVIOUS',
      '  PF8  = SCROLL DOWN / INQUIRE',
      '  PF9  = NEXT RECORD',
      '  PF12 = VIEW COBOL/SQL CODE',
    ]
  },
  CUST: {
    title: 'CUSTMNT - CUSTOMER MAINTENANCE HELP',
    lines: [
      'CUSTMNT  -  CUSTOMER MASTER MAINTENANCE PROGRAM',
      '',
      'FIELD DESCRIPTIONS:',
      '  CUSTOMER-ID  : 8-DIGIT UNIQUE CUSTOMER IDENTIFIER',
      '                 SYSTEM ASSIGNED ON ADD. ENTER TO INQUIRE.',
      '  SURNAME      : CUSTOMER SURNAME, MAX 30 CHARACTERS',
      '  FORENAME     : CUSTOMER FORENAME, MAX 20 CHARACTERS',
      '  DATE-OF-BIRTH: FORMAT DD/MM/YY  (EG 25/12/58)',
      '  SORT-CODE    : 6-DIGIT BRANCH SORT CODE (NO DASHES)',
      '  NI NUMBER    : NATIONAL INSURANCE NUMBER (9 CHARS)',
      '                 FORMAT: AB123456C',
      '  ADDRESS 1-3  : STREET, TOWN, COUNTY LINES',
      '  POSTCODE     : UK POSTCODE (MAX 8 CHARS)',
      '  STATUS       : A = ACTIVE   I = INACTIVE   D = DELETED',
      '  CUST TYPE    : P = PERSONAL CUSTOMER',
      '                 C = CORPORATE / BUSINESS CUSTOMER',
      '',
      'AVAILABLE ACTIONS:',
      '  PF5  = ADD    : ADD NEW CUSTOMER RECORD',
      '  PF6  = UPDATE : MODIFY EXISTING CUSTOMER',
      '  PF7  = DELETE : MARK CUSTOMER AS DELETED (LOGICAL)',
      '  PF8  = INQUIRE: RETRIEVE CUSTOMER BY ID',
      '',
      'CICS RESPONSE CODES:',
      '  NORMAL  = OPERATION COMPLETED SUCCESSFULLY',
      '  NOTFND  = CUSTOMER ID NOT FOUND IN DATABASE',
      '  DUPKEY  = CUSTOMER ID ALREADY EXISTS (ON ADD)',
      '  INVREQ  = INVALID REQUEST / MISSING REQUIRED FIELD',
    ]
  },
  ACCT: {
    title: 'ACCTMNT - ACCOUNT MAINTENANCE HELP',
    lines: [
      'ACCTMNT  -  ACCOUNT MAINTENANCE PROGRAM',
      '',
      'FIELD DESCRIPTIONS:',
      '  ACCOUNT-NUMBER: 10-DIGIT UNIQUE ACCOUNT NUMBER',
      '  CUSTOMER-ID   : LINKED CUSTOMER (MUST EXIST IN CUSTMAST)',
      '  ACCOUNT TYPE  : SAV = SAVINGS ACCOUNT',
      '                  CUR = CURRENT ACCOUNT (CHEQUE)',
      '                  OVD = OVERDRAFT FACILITY',
      '                  LON = LOAN ACCOUNT',
      '  SORT-CODE     : 6-DIGIT BRANCH IDENTIFIER',
      '  CURRENCY      : GBP  USD  EUR',
      '  BALANCE       : CURRENT CLEARED BALANCE (SIGNED 13.2)',
      '                  NEGATIVE BALANCE SHOWN WITH MINUS SIGN',
      '  CREDIT LIMIT  : AUTHORISED CREDIT/OVERDRAFT LIMIT',
      '  INTEREST RATE : ANNUAL RATE AS PERCENTAGE (EG 7.50)',
      '  STATUS        : A = ACTIVE   D = DORMANT   F = FROZEN',
      '',
      'AVAILABLE ACTIONS:',
      '  PF5  = OPEN   : OPEN NEW ACCOUNT FOR CUSTOMER',
      '  PF6  = MODIFY : AMEND ACCOUNT TERMS',
      '  PF8  = INQUIRE: RETRIEVE ACCOUNT DETAILS',
      '  PF9  = NEXT   : NEXT ACCOUNT FOR SAME CUSTOMER',
      '',
      'NOTE: BALANCE IS UPDATED AUTOMATICALLY BY TRANPST.',
      'DO NOT MANUALLY AMEND BALANCE WITHOUT AUTHORISATION.',
    ]
  },
  TRAN: {
    title: 'TRANPST - TRANSACTION POSTING HELP',
    lines: [
      'TRANPST  -  TRANSACTION POSTING PROGRAM',
      '',
      'FIELD DESCRIPTIONS:',
      '  ACCOUNT-NUMBER: 10-DIGIT ACCOUNT TO POST AGAINST',
      '  TRAN TYPE     : CR  = CREDIT  (MONEY IN)',
      '                  DR  = DEBIT   (MONEY OUT)',
      '                  TRF = TRANSFER BETWEEN ACCOUNTS',
      '  AMOUNT        : TRANSACTION AMOUNT (MAX 13 DIGITS, 2 DP)',
      '                  DO NOT INCLUDE CURRENCY SYMBOL',
      '  DESCRIPTION   : FREE TEXT NARRATIVE (MAX 40 CHARS)',
      '  REFERENCE     : PAYMENT REFERENCE (MAX 12 CHARS)',
      '  TO-ACCOUNT    : DESTINATION ACCOUNT FOR TRF TYPE ONLY',
      '  VALUE DATE    : EFFECTIVE DATE  FORMAT DD/MM/YY',
      '',
      'AVAILABLE ACTIONS:',
      '  PF5  = POST   : SUBMIT TRANSACTION FOR POSTING',
      '  PF8  = HISTORY: VIEW TRANSACTION HISTORY FOR ACCOUNT',
      '',
      'HISTORY SCREEN NAVIGATION:',
      '  PF7  = SCROLL UP   (PREVIOUS TRANSACTIONS)',
      '  PF8  = SCROLL DOWN (LATER TRANSACTIONS)',
      '  PF3  = RETURN TO POSTING SCREEN',
      '',
      'IMPORTANT: ALL TRANSACTIONS ARE LOGGED IN DB2 TRANLOG.',
      'ACCOUNT BALANCE IS UPDATED IMMEDIATELY ON POSTING.',
      'TRANSFERS CREATE TWO ENTRIES: DR ON FROM, CR ON TO.',
    ]
  }
};

export default function HelpOverlay({ screen, onClose }) {
  const content = HELP_CONTENT[screen] || HELP_CONTENT['MENU'];

  return (
    <div style={{
      position: 'absolute',
      top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: '#000000',
      zIndex: 200,
      fontFamily: "'Courier New', Courier, monospace",
      fontSize: '13px',
      display: 'flex',
      flexDirection: 'column',
      padding: '8px',
    }}>
      <div style={{
        color: '#AAFFAA',
        fontWeight: 'bold',
        marginBottom: '8px',
        borderBottom: '1px solid #33FF33',
        paddingBottom: '4px',
        fontSize: '14px',
      }}>
        {'IBM CICS/VS  ONLINE HELP FACILITY  '.padEnd(50)}
        <span style={{ color: '#33FF33' }}>PF1/PF3=RETURN</span>
      </div>

      <div style={{
        color: '#AAFFAA',
        fontWeight: 'bold',
        marginBottom: '8px',
        textDecoration: 'underline',
      }}>
        {content.title}
      </div>

      <div style={{
        flex: 1,
        overflowY: 'auto',
        color: '#33FF33',
        lineHeight: '1.8',
        whiteSpace: 'pre',
      }}>
        {content.lines.map((line, i) => (
          <div key={i} style={{
            color: line.startsWith('  ') && line.includes(':') ? '#33FF33' :
                   line.endsWith(':') ? '#AAFFAA' : '#33FF33'
          }}>
            {line}
          </div>
        ))}
      </div>

      <button
        onClick={onClose}
        style={{
          marginTop: '8px',
          background: '#001100',
          border: '1px solid #AAFFAA',
          color: '#AAFFAA',
          fontFamily: 'inherit',
          fontSize: '13px',
          padding: '4px',
          cursor: 'pointer',
          fontWeight: 'bold',
        }}
      >
        PF1/PF3 - RETURN TO TRANSACTION SCREEN
      </button>
    </div>
  );
}