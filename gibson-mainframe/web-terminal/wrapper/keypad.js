// Gibson v30.286-freeze keypad marker file.
// Runtime keypad logic is generated into generated/wrapper-root/index.html and uses
// guacamole-common-js with Guacamole.Client.sendKeyEvent(). No iframe key injection
// or alert popup workaround is used.
const GIBSON_KEYPAD_MODE = 'guacamole-common-js-direct-client';
const GIBSON_KEYSYMS = { PF3: 0xffc0, PF7: 0xffc4, PF8: 0xffc5, ENTER: 0xff0d, TAB: 0xff09 };
const GIBSON_SYMBOLIC_FALLBACKS = { PA1: 'PA1\r', PA2: 'PA2\r', CLEAR: 'CLEAR\r', RESET: 'RESET\r' };
function sendKeysym(client, keysym) { client.sendKeyEvent(1, keysym); client.sendKeyEvent(0, keysym); }
function sendText(client, text) { for (const ch of text) sendKeysym(client, ch === '\r' ? 0xff0d : ch.codePointAt(0)); }
