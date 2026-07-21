import React, { useState } from 'react';
import { base44 } from '@/api/base44Client';

const S = {
  mono: "'Courier New', monospace",
  green: '#33FF33',
  bright: '#AAFFAA',
  blue: '#3399FF',
  yellow: '#FFFF00',
  red: '#FF3333',
  grey: '#668866',
  neutral: '#AAAAAA',
};

// Static product catalogue matching real DVCA VSAM data
const PRODUCTS = [
  { id: '00001', name: 'Ballpoint Pens (box of 12)',       price: 4.99,   shipping: 2.99,  purchasable: 'Y', comment: 'Office Supply' },
  { id: '00002', name: 'Sticky Notes 3x3 (24 pads)',       price: 12.99,  shipping: 3.99,  purchasable: 'Y', comment: 'Office Supply' },
  { id: '00003', name: 'Stapler - Heavy Duty',             price: 18.50,  shipping: 4.99,  purchasable: 'Y', comment: 'Office Supply' },
  { id: '00004', name: 'A4 Paper (500 sheets)',            price: 6.99,   shipping: 5.99,  purchasable: 'Y', comment: 'Office Supply' },
  { id: '00005', name: 'Scotch Tape (6 roll multipack)',   price: 7.50,   shipping: 2.99,  purchasable: 'Y', comment: 'Office Supply' },
  { id: '00006', name: 'Whiteboard Markers (set of 8)',    price: 9.99,   shipping: 2.99,  purchasable: 'Y', comment: 'Office Supply' },
  { id: '00007', name: 'Filing Folders (pack of 50)',      price: 14.99,  shipping: 3.99,  purchasable: 'Y', comment: 'Office Supply' },
  { id: '00008', name: 'Vintage Scotch Whisky 12yr',       price: 65.00,  shipping: 8.99,  purchasable: 'N', comment: 'BANNED - BOOZE' },
  { id: '00009', name: 'Gold Idol Replica (prop)',         price: 299.00, shipping: 19.99, purchasable: 'N', comment: 'BANNED - IDOL' },
  { id: '00010', name: 'Ergonomic Office Chair',           price: 249.99, shipping: 24.99, purchasable: 'Y', comment: 'Furniture' },
];

export default function DvcaMcor({ operatorId, onNavigate, hackFields, onApiLeak, onLog }) {
  const [idx, setIdx] = useState(0);
  const [message, setMessage] = useState('OFFICE SUPPLIES PRICE LIST - PF7/PF8 TO BROWSE');
  const [msgType, setMsgType] = useState('normal');
  const [ordering, setOrdering] = useState(false);
  const [orderDone, setOrderDone] = useState(null);

  // VULN: FSET — price field is PROT,FSET — can be overtyped if protection removed
  const [priceOverride, setPriceOverride] = useState(null);

  const product = PRODUCTS[idx];
  const displayPrice = priceOverride !== null ? priceOverride : product.price;

  const protectionDisabled = hackFields?.master && hackFields?.disable_field_protection;
  const hiddenExposed = hackFields?.master && hackFields?.enable_hidden_fields;

  const handlePrev = () => {
    setIdx(i => Math.max(0, i - 1));
    setPriceOverride(null);
    setOrderDone(null);
    setMessage('PREVIOUS RECORD');
    setMsgType('normal');
  };

  const handleNext = () => {
    setIdx(i => Math.min(PRODUCTS.length - 1, i + 1));
    setPriceOverride(null);
    setOrderDone(null);
    setMessage('NEXT RECORD');
    setMsgType('normal');
  };

  const handleOrder = async () => {
    // VULN: purchasable field is hidden — if hack3270 exposes it, banned items can be ordered
    if (product.purchasable === 'N' && !hiddenExposed) {
      setMessage(`ITEM NOT AVAILABLE FOR PURCHASE: ${product.comment}`);
      setMsgType('error');
      if (onLog) onLog({ type: 'warn', text: `ORDER BLOCKED: ${product.name} — PURCHASABLE=N` });
      return;
    }
    if (product.purchasable === 'N' && hiddenExposed) {
      // Hack3270 changed hidden PURCHASABLE field from N to Y
      if (onLog) onLog({ type: 'warn', text: `⚠ VULN: BANNED ITEM ORDERED BY OVERRIDING HIDDEN PURCHASABLE FIELD: ${product.name}` });
      if (onApiLeak) onApiLeak(`HIDDEN FIELD EXPLOIT: PURCHASABLE='N' overridden — ordered banned item: ${product.name}`);
    }
    if (priceOverride !== null && protectionDisabled) {
      if (onLog) onLog({ type: 'warn', text: `⚠ VULN FSET: PRICE MODIFIED from $${product.price} to $${priceOverride} — ORDERED AT MANIPULATED PRICE` });
      if (onApiLeak) onApiLeak(`FSET VULN: Price for '${product.name}' changed from $${product.price} to $${priceOverride}`);
    }

    setOrdering(true);
    // Simulate creating a transaction record
    try {
      await base44.entities.Transaction.create({
        tran_id: 'MC' + String(Date.now()).slice(-8),
        account_number: 'MELSCARGO',
        tran_type: 'DR',
        amount: parseFloat(displayPrice),
        description: `ORDER: ${product.name}`,
        reference: product.id,
        post_date: new Date().toLocaleDateString('en-GB'),
        post_time: new Date().toLocaleTimeString('en-GB', { hour12: false }).replace(/:/g, ''),
        balance_after: 0,
        operator_id: operatorId || 'DVCA',
      });
    } catch (_) { /* non-critical */ }

    setOrderDone({ name: product.name, price: displayPrice });
    setMessage(`ORDER PLACED: ${product.name} — $${parseFloat(displayPrice).toFixed(2)} + SHIPPING $${product.shipping.toFixed(2)}`);
    setMsgType('success');
    setOrdering(false);
  };

  const handleKey = (e) => {
    if (e.key === 'F7') { e.preventDefault(); handlePrev(); }
    if (e.key === 'F8') { e.preventDefault(); handleNext(); }
    if (e.key === 'F5') onNavigate('MCMM');
    if (e.key === 'F3') onNavigate('MCMM');
    if (e.key === 'Enter') handleOrder();
  };

  const msgColor = msgType === 'error' ? S.red : msgType === 'success' ? S.bright : S.green;

  return (
    <div
      onKeyDown={handleKey}
      tabIndex={0}
      style={{ flex: 1, padding: '8px', fontFamily: S.mono, fontSize: '13px', background: '#000', overflowY: 'auto', outline: 'none' }}
    >
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px' }}>
        <span style={{ color: S.blue }}>MCOR</span>
        <span style={{ color: S.yellow, fontWeight: 'bold' }}>Mels Cargo — Office Supplies Price List</span>
        <span style={{ color: S.blue }}>MCOR</span>
      </div>
      <div style={{ color: S.blue, marginBottom: '8px' }}>{'─'.repeat(79)}</div>

      {/* Record number */}
      <div style={{ color: S.grey, fontSize: '11px', marginBottom: '6px' }}>
        RECORD: {product.id} / {PRODUCTS.length.toString().padStart(5, '0')} &nbsp;&nbsp; 
        {hiddenExposed && <span style={{ color: '#FF9933' }}>⚠ HIDDEN FIELDS EXPOSED BY HACK3270</span>}
        {protectionDisabled && <span style={{ color: S.red }}> ⚠ FIELD PROTECTION DISABLED</span>}
      </div>

      {/* Product fields */}
      <div style={{ lineHeight: '2.0' }}>
        <div style={{ display: 'flex', gap: '4px' }}>
          <span style={{ color: S.bright, width: '22ch' }}>Product Name      :</span>
          {/* FSET vuln: field is PROT,FSET — should be protected but FSET means content is sent back */}
          <span style={{ color: S.neutral, width: '36ch' }}>{product.name}</span>
        </div>

        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
          <span style={{ color: S.bright, width: '22ch' }}>Price             :</span>
          {protectionDisabled ? (
            // VULN: FSET — protection disabled, price can be overtyped
            <input
              value={priceOverride !== null ? priceOverride : product.price}
              onChange={e => setPriceOverride(e.target.value)}
              style={{
                background: '#001a00', border: `1px solid ${S.red}`, color: S.yellow,
                fontFamily: S.mono, fontSize: '13px', outline: 'none', width: '12ch',
              }}
            />
          ) : (
            <span style={{ color: S.neutral }}>${product.price.toFixed(2)}</span>
          )}
          {protectionDisabled && priceOverride !== null && (
            <span style={{ color: S.red, fontSize: '10px', marginLeft: '6px' }}>⚠ FSET VULN: MODIFIED</span>
          )}
        </div>

        <div style={{ display: 'flex', gap: '4px' }}>
          <span style={{ color: S.bright, width: '22ch' }}>Shipping          :</span>
          <span style={{ color: S.neutral }}>${product.shipping.toFixed(2)}</span>
        </div>

        <div style={{ display: 'flex', gap: '4px' }}>
          <span style={{ color: S.bright, width: '22ch' }}>Item Number       :</span>
          <span style={{ color: S.neutral }}>{product.id}</span>
        </div>

        {/* Hidden PURCHASABLE field */}
        <div style={{ display: 'flex', gap: '4px', alignItems: 'center' }}>
          <span style={{ color: hiddenExposed ? '#FF9933' : '#111111', width: '22ch' }}>
            {hiddenExposed ? 'Purchasable [HIDDEN]:' : '                      '}
          </span>
          <span style={{ color: hiddenExposed ? (product.purchasable === 'Y' ? S.bright : S.red) : '#111111' }}>
            {hiddenExposed ? product.purchasable : ''}
          </span>
          {hiddenExposed && product.purchasable === 'N' && (
            <span style={{ color: S.red, fontSize: '10px' }}>⚠ BANNED ITEM — HIDDEN FIELD SAYS N</span>
          )}
        </div>

        <div style={{ display: 'flex', gap: '4px' }}>
          <span style={{ color: S.bright, width: '22ch' }}>Comment           :</span>
          <span style={{ color: product.comment.includes('BANNED') ? S.red : S.grey }}>{product.comment}</span>
        </div>
      </div>

      <div style={{ color: S.blue, margin: '6px 0' }}>{'─'.repeat(79)}</div>

      {/* Message */}
      <div style={{ color: msgColor, fontWeight: 'bold', minHeight: '1.4em' }}>{message}</div>

      {/* PF key guide */}
      <div style={{ color: S.blue, fontSize: '11px', marginTop: '4px' }}>
        PF1 - Help &nbsp;&nbsp; PF3/PF5 - Main Menu &nbsp;&nbsp; PF7 - Prev &nbsp;&nbsp; PF8 - Next &nbsp;&nbsp; ENTER - Order
      </div>

      {/* Buttons */}
      <div style={{ marginTop: '8px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        <button onClick={handlePrev} disabled={idx === 0} style={btnStyle(S.blue, idx === 0)}>PF7 PREV</button>
        <button onClick={handleNext} disabled={idx === PRODUCTS.length - 1} style={btnStyle(S.blue, idx === PRODUCTS.length - 1)}>PF8 NEXT</button>
        <button onClick={handleOrder} disabled={ordering} style={btnStyle(S.bright)}>ENTER ORDER</button>
        <button onClick={() => onNavigate('MCMM')} style={btnStyle(S.grey)}>PF5 MENU</button>
      </div>

      {/* Vulnerability hints */}
      {!hackFields?.master && (
        <div style={{ marginTop: '8px', color: '#224422', fontSize: '11px' }}>
          HINT: Enable HACK3270 to expose hidden fields (PURCHASABLE) and disable FSET field protection
        </div>
      )}
    </div>
  );
}

function btnStyle(color, disabled = false) {
  return {
    background: '#001100', border: `1px solid ${disabled ? '#224422' : color}`,
    color: disabled ? '#224422' : color,
    fontFamily: "'Courier New', monospace",
    fontSize: '11px', padding: '2px 10px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: disabled ? 0.5 : 1,
  };
}