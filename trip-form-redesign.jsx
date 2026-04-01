import { useState, useEffect } from "react";

const STEPS = [
  { id: "role", label: "Роль", icon: "👤" },
  { id: "participants", label: "Участники", icon: "🤝" },
  { id: "route", label: "Маршрут", icon: "📍" },
  { id: "cargo", label: "Груз", icon: "📦" },
  { id: "finance", label: "Финансы", icon: "💰" },
];

const ROLES = [
  {
    id: "customer",
    title: "Заказчик",
    desc: "Моя фирма заказывает перевозку",
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
        <path d="M16 3.13a4 4 0 0 1 0 7.75" />
      </svg>
    ),
  },
  {
    id: "carrier",
    title: "Перевозчик",
    desc: "Моя фирма выполняет перевозку",
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <rect x="1" y="3" width="15" height="13" rx="2" />
        <path d="M16 8h4l3 3v5h-7V8z" />
        <circle cx="5.5" cy="18.5" r="2.5" />
        <circle cx="18.5" cy="18.5" r="2.5" />
      </svg>
    ),
  },
  {
    id: "forwarder",
    title: "Экспедитор",
    desc: "Я нахожу груз и транспорт",
    icon: (
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
        <path d="M9 12l2 2 4-4" />
      </svg>
    ),
  },
];

const fonts = `
@import url('https://fonts.googleapis.com/css2?family=Onest:wght@300;400;500;600;700&display=swap');
`;

export default function TripFormRedesign() {
  const [step, setStep] = useState(0);
  const [role, setRole] = useState(null);
  const [animDir, setAnimDir] = useState("next");

  const [customerRate, setCustomerRate] = useState("");
  const [carrierRate, setCarrierRate] = useState("");
  const [currency, setCurrency] = useState("RUB");
  const [paymentForm, setPaymentForm] = useState("");
  const [paymentDays, setPaymentDays] = useState("5");
  const [paymentOnUnload, setPaymentOnUnload] = useState(false);

  const [paymentFormCarrier, setPaymentFormCarrier] = useState("");
  const [paymentDaysCarrier, setPaymentDaysCarrier] = useState("5");
  const [paymentOnUnloadCarrier, setPaymentOnUnloadCarrier] = useState(false);

  const goNext = () => {
    if (step < STEPS.length - 1) {
      setAnimDir("next");
      setStep(step + 1);
    }
  };
  const goPrev = () => {
    if (step > 0) {
      setAnimDir("prev");
      setStep(step - 1);
    }
  };
  const goToStep = (i) => {
    setAnimDir(i > step ? "next" : "prev");
    setStep(i);
  };

  const margin =
    customerRate && carrierRate
      ? Number(customerRate) - Number(carrierRate)
      : null;
  const marginPct =
    margin !== null && Number(customerRate) > 0
      ? Math.round((margin / Number(customerRate)) * 100)
      : null;

  return (
    <>
      <style>{fonts}{`
        * { box-sizing: border-box; margin: 0; padding: 0; }
        .trip-form {
          font-family: 'Onest', system-ui, sans-serif;
          max-width: 720px;
          margin: 0 auto;
          color: #1a1a2e;
          -webkit-font-smoothing: antialiased;
        }

        /* Header */
        .form-header {
          padding: 28px 0 24px;
          border-bottom: 1px solid #e8e8ee;
          margin-bottom: 32px;
        }
        .form-header h1 {
          font-size: 22px;
          font-weight: 600;
          letter-spacing: -0.3px;
          color: #1a1a2e;
        }
        .form-header p {
          font-size: 13px;
          color: #8b8b9e;
          margin-top: 4px;
        }

        /* Stepper */
        .stepper {
          display: flex;
          gap: 4px;
          margin-bottom: 36px;
          position: sticky;
          top: 0;
          z-index: 10;
          background: #fff;
          padding: 12px 0;
        }
        .step-item {
          flex: 1;
          cursor: pointer;
          border: none;
          background: none;
          text-align: center;
          padding: 0;
          position: relative;
        }
        .step-bar {
          height: 3px;
          border-radius: 2px;
          background: #e8e8ee;
          margin-bottom: 10px;
          transition: background 0.3s ease;
          overflow: hidden;
        }
        .step-bar::after {
          content: '';
          display: block;
          height: 100%;
          width: 0%;
          background: #3366ff;
          border-radius: 2px;
          transition: width 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .step-item.done .step-bar::after,
        .step-item.active .step-bar::after {
          width: 100%;
        }
        .step-item.done .step-bar::after {
          background: #22c55e;
        }
        .step-label {
          font-size: 11px;
          font-weight: 500;
          color: #b0b0c0;
          letter-spacing: 0.3px;
          text-transform: uppercase;
          transition: color 0.3s;
        }
        .step-item.active .step-label {
          color: #3366ff;
        }
        .step-item.done .step-label {
          color: #22c55e;
        }

        /* Content area */
        .step-content {
          min-height: 420px;
          animation: fadeSlide 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        }
        @keyframes fadeSlide {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }

        .section-title {
          font-size: 17px;
          font-weight: 600;
          color: #1a1a2e;
          margin-bottom: 6px;
          letter-spacing: -0.2px;
        }
        .section-desc {
          font-size: 13px;
          color: #8b8b9e;
          margin-bottom: 28px;
          line-height: 1.5;
        }

        /* Role cards */
        .role-grid {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: 12px;
        }
        .role-card {
          border: 1.5px solid #e8e8ee;
          border-radius: 14px;
          padding: 24px 16px;
          text-align: center;
          cursor: pointer;
          transition: all 0.25s ease;
          background: #fff;
          position: relative;
        }
        .role-card:hover {
          border-color: #c0c0d0;
          transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(0,0,0,0.06);
        }
        .role-card.selected {
          border-color: #3366ff;
          background: #f0f4ff;
          box-shadow: 0 0 0 3px rgba(51,102,255,0.12);
        }
        .role-icon {
          width: 52px;
          height: 52px;
          border-radius: 14px;
          background: #f4f4f8;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 14px;
          color: #6b6b80;
          transition: all 0.25s;
        }
        .role-card.selected .role-icon {
          background: #3366ff;
          color: #fff;
        }
        .role-card h3 {
          font-size: 14px;
          font-weight: 600;
          margin-bottom: 4px;
          color: #1a1a2e;
        }
        .role-card p {
          font-size: 12px;
          color: #8b8b9e;
          line-height: 1.4;
        }
        .role-check {
          position: absolute;
          top: 10px;
          right: 10px;
          width: 22px;
          height: 22px;
          border-radius: 50%;
          background: #3366ff;
          display: flex;
          align-items: center;
          justify-content: center;
          opacity: 0;
          transform: scale(0.5);
          transition: all 0.25s;
        }
        .role-card.selected .role-check {
          opacity: 1;
          transform: scale(1);
        }

        /* Form fields */
        .field-group {
          margin-bottom: 20px;
        }
        .field-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 16px;
        }
        .field-label {
          display: block;
          font-size: 13px;
          font-weight: 500;
          color: #4a4a5e;
          margin-bottom: 6px;
        }
        .field-label .req {
          color: #ef4444;
          margin-left: 2px;
        }
        .field-hint {
          font-size: 11px;
          color: #a0a0b4;
          margin-top: 4px;
          line-height: 1.4;
        }
        .field-input {
          width: 100%;
          height: 42px;
          border: 1.5px solid #e0e0ea;
          border-radius: 10px;
          padding: 0 14px;
          font-size: 14px;
          font-family: inherit;
          color: #1a1a2e;
          background: #fff;
          transition: all 0.2s;
          outline: none;
        }
        .field-input:hover {
          border-color: #c0c0d4;
        }
        .field-input:focus {
          border-color: #3366ff;
          box-shadow: 0 0 0 3px rgba(51,102,255,0.1);
        }
        .field-input::placeholder {
          color: #c0c0cc;
        }
        .field-textarea {
          height: 80px;
          padding: 12px 14px;
          resize: vertical;
        }
        .field-select {
          appearance: none;
          background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%238b8b9e' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
          background-repeat: no-repeat;
          background-position: right 14px center;
          padding-right: 36px;
        }

        /* Dual panel */
        .dual-panel {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 0;
          border: 1.5px solid #e0e0ea;
          border-radius: 14px;
          overflow: hidden;
          margin-bottom: 20px;
        }
        .dual-side {
          padding: 20px;
        }
        .dual-side:first-child {
          border-right: 1px solid #e8e8ee;
        }
        .dual-side-header {
          display: flex;
          align-items: center;
          gap: 8px;
          margin-bottom: 16px;
          padding-bottom: 12px;
          border-bottom: 1px solid #f0f0f4;
        }
        .dual-side-dot {
          width: 8px;
          height: 8px;
          border-radius: 50%;
        }
        .dual-side-title {
          font-size: 13px;
          font-weight: 600;
          color: #1a1a2e;
          letter-spacing: -0.1px;
        }

        /* Address with dot connector */
        .route-visual {
          display: flex;
          gap: 16px;
          margin-bottom: 24px;
        }
        .route-line {
          display: flex;
          flex-direction: column;
          align-items: center;
          padding-top: 6px;
          gap: 0;
          width: 20px;
          flex-shrink: 0;
        }
        .route-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          border: 2.5px solid #22c55e;
          background: #fff;
          flex-shrink: 0;
        }
        .route-dot.end {
          border-color: #ef4444;
        }
        .route-dash {
          width: 2px;
          flex: 1;
          min-height: 36px;
          background: repeating-linear-gradient(to bottom, #d0d0dd 0, #d0d0dd 4px, transparent 4px, transparent 8px);
        }
        .route-fields {
          flex: 1;
          display: flex;
          flex-direction: column;
          gap: 16px;
        }
        .route-block {
          background: #f8f8fb;
          border-radius: 12px;
          padding: 16px;
        }
        .route-block-title {
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          margin-bottom: 12px;
        }
        .route-block-title.load { color: #16a34a; }
        .route-block-title.unload { color: #dc2626; }

        /* Cargo chips */
        .cargo-specs {
          display: grid;
          grid-template-columns: 1fr 1fr 1fr;
          gap: 12px;
          margin-top: 16px;
        }
        .spec-card {
          background: #f4f4f8;
          border-radius: 12px;
          padding: 16px;
          text-align: center;
        }
        .spec-card label {
          font-size: 11px;
          color: #8b8b9e;
          text-transform: uppercase;
          letter-spacing: 0.4px;
          font-weight: 500;
          display: block;
          margin-bottom: 8px;
        }
        .spec-card input {
          width: 100%;
          text-align: center;
          border: none;
          background: #fff;
          border-radius: 8px;
          height: 38px;
          font-size: 16px;
          font-weight: 600;
          font-family: inherit;
          color: #1a1a2e;
          outline: none;
          border: 1.5px solid transparent;
          transition: border-color 0.2s;
        }
        .spec-card input:focus {
          border-color: #3366ff;
        }
        .spec-card .unit {
          font-size: 11px;
          color: #a0a0b4;
          margin-top: 4px;
        }

        /* Finance cards */
        .finance-card {
          border: 1.5px solid #e0e0ea;
          border-radius: 14px;
          padding: 24px;
          margin-bottom: 16px;
          position: relative;
          transition: all 0.25s;
        }
        .finance-card.income {
          border-color: #bbf7d0;
          background: linear-gradient(135deg, #f0fdf4 0%, #fff 100%);
        }
        .finance-card.expense {
          border-color: #fecaca;
          background: linear-gradient(135deg, #fef2f2 0%, #fff 100%);
        }
        .finance-card.neutral {
          background: #fafafe;
        }
        .finance-tag {
          display: inline-flex;
          align-items: center;
          gap: 5px;
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          padding: 4px 10px;
          border-radius: 6px;
          margin-bottom: 14px;
        }
        .finance-tag.income {
          background: #dcfce7;
          color: #15803d;
        }
        .finance-tag.expense {
          background: #fee2e2;
          color: #b91c1c;
        }
        .finance-tag.neutral {
          background: #f0f0f8;
          color: #6b6b80;
        }
        .finance-amount-row {
          display: flex;
          align-items: center;
          gap: 10px;
          margin-bottom: 16px;
        }
        .finance-amount-input {
          flex: 1;
          height: 48px;
          border: 1.5px solid #e0e0ea;
          border-radius: 10px;
          padding: 0 16px;
          font-size: 20px;
          font-weight: 600;
          font-family: inherit;
          color: #1a1a2e;
          background: #fff;
          outline: none;
          transition: all 0.2s;
        }
        .finance-amount-input:focus {
          border-color: #3366ff;
          box-shadow: 0 0 0 3px rgba(51,102,255,0.1);
        }
        .currency-badge {
          height: 48px;
          padding: 0 16px;
          border: 1.5px solid #e0e0ea;
          border-radius: 10px;
          background: #f8f8fb;
          font-size: 14px;
          font-weight: 600;
          color: #6b6b80;
          display: flex;
          align-items: center;
          font-family: inherit;
          cursor: pointer;
        }
        .payment-details {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 12px;
          padding-top: 16px;
          border-top: 1px solid #f0f0f4;
        }

        /* Margin banner */
        .margin-banner {
          background: linear-gradient(135deg, #1a1a2e 0%, #2d2d4e 100%);
          border-radius: 14px;
          padding: 20px 24px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
          color: #fff;
        }
        .margin-label {
          font-size: 13px;
          color: rgba(255,255,255,0.6);
          font-weight: 500;
        }
        .margin-value {
          font-size: 26px;
          font-weight: 700;
          letter-spacing: -0.5px;
        }
        .margin-pct {
          font-size: 14px;
          font-weight: 600;
          padding: 4px 12px;
          border-radius: 8px;
          background: rgba(255,255,255,0.15);
        }
        .margin-pct.positive { color: #4ade80; }
        .margin-pct.negative { color: #f87171; }
        .margin-pct.zero { color: rgba(255,255,255,0.5); }

        /* Footer */
        .form-footer {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 24px 0;
          margin-top: 12px;
          border-top: 1px solid #e8e8ee;
        }
        .btn {
          height: 44px;
          padding: 0 28px;
          border-radius: 10px;
          font-size: 14px;
          font-weight: 600;
          font-family: inherit;
          cursor: pointer;
          transition: all 0.2s;
          border: none;
          display: inline-flex;
          align-items: center;
          gap: 8px;
        }
        .btn-primary {
          background: #3366ff;
          color: #fff;
        }
        .btn-primary:hover {
          background: #2952cc;
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(51,102,255,0.3);
        }
        .btn-secondary {
          background: transparent;
          color: #6b6b80;
          border: 1.5px solid #e0e0ea;
        }
        .btn-secondary:hover {
          background: #f4f4f8;
          color: #1a1a2e;
        }
        .btn-ghost {
          background: transparent;
          color: #8b8b9e;
        }
        .btn-ghost:hover {
          color: #1a1a2e;
        }
        .btn-save {
          background: #1a1a2e;
          color: #fff;
        }
        .btn-save:hover {
          background: #2d2d4e;
          transform: translateY(-1px);
          box-shadow: 0 4px 16px rgba(26,26,46,0.25);
        }

        /* Info auto-field */
        .auto-field {
          background: #f8f8fb;
          border: 1.5px dashed #d8d8e4;
          border-radius: 10px;
          padding: 10px 14px;
          font-size: 13px;
          color: #a0a0b4;
          display: flex;
          align-items: center;
          gap: 8px;
        }

        /* Search input */
        .search-input-wrap {
          position: relative;
        }
        .search-input-wrap .field-input {
          padding-left: 36px;
        }
        .search-icon {
          position: absolute;
          left: 12px;
          top: 50%;
          transform: translateY(-50%);
          color: #c0c0cc;
        }

        /* Radio group */
        .radio-group {
          display: flex;
          gap: 8px;
        }
        .radio-pill {
          flex: 1;
          cursor: pointer;
        }
        .radio-pill input { display: none; }
        .radio-pill span {
          display: block;
          text-align: center;
          padding: 8px 12px;
          border: 1.5px solid #e0e0ea;
          border-radius: 8px;
          font-size: 13px;
          color: #6b6b80;
          font-weight: 500;
          transition: all 0.2s;
        }
        .radio-pill input:checked + span {
          border-color: #3366ff;
          background: #f0f4ff;
          color: #3366ff;
        }

        /* Pre-filled chip */
        .prefilled-chip {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          background: #f0f4ff;
          border: 1.5px solid #bfdbfe;
          border-radius: 10px;
          padding: 10px 14px;
          font-size: 14px;
          color: #1e40af;
          font-weight: 500;
        }
        .prefilled-chip .remove-btn {
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #dbeafe;
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          color: #3b82f6;
          font-size: 12px;
          transition: background 0.2s;
        }
        .prefilled-chip .remove-btn:hover {
          background: #bfdbfe;
        }
        .auto-badge {
          font-size: 10px;
          background: #dbeafe;
          color: #1d4ed8;
          padding: 2px 6px;
          border-radius: 4px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.3px;
        }
      `}</style>

      <div className="trip-form">
        {/* Header */}
        <div className="form-header">
          <h1>Создать рейс</h1>
          <p>Заполните данные по заявке, участникам и условиям перевозки</p>
        </div>

        {/* Stepper */}
        <div className="stepper">
          {STEPS.map((s, i) => (
            <button
              key={s.id}
              className={`step-item ${i === step ? "active" : ""} ${i < step ? "done" : ""}`}
              onClick={() => goToStep(i)}
            >
              <div className="step-bar" />
              <span className="step-label">{s.label}</span>
            </button>
          ))}
        </div>

        {/* Step content */}
        <div className="step-content" key={step}>
          {/* STEP 0: Role */}
          {step === 0 && (
            <div>
              <div className="section-title">Моя роль в перевозке</div>
              <div className="section-desc">
                Выберите, в каком качестве вы участвуете. Это определит, какие
                поля будут показаны далее.
              </div>

              <div className="role-grid">
                {ROLES.map((r) => (
                  <div
                    key={r.id}
                    className={`role-card ${role === r.id ? "selected" : ""}`}
                    onClick={() => setRole(r.id)}
                  >
                    <div className="role-check">
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M2 6l3 3 5-5" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    </div>
                    <div className="role-icon">{r.icon}</div>
                    <h3>{r.title}</h3>
                    <p>{r.desc}</p>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: 24 }}>
                <div className="field-row">
                  <div className="field-group">
                    <label className="field-label">Номер заявки</label>
                    <div className="auto-field">
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M13 3H3a1 1 0 00-1 1v8a1 1 0 001 1h10a1 1 0 001-1V4a1 1 0 00-1-1z"/><path d="M5 7h6M5 10h3"/></svg>
                      Присвоится автоматически
                    </div>
                  </div>
                  <div className="field-group">
                    <label className="field-label">
                      Дата заявки<span className="req">*</span>
                    </label>
                    <input type="date" className="field-input" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 1: Participants */}
          {step === 1 && (
            <div>
              <div className="section-title">Участники перевозки</div>
              <div className="section-desc">
                {role === "customer"
                  ? "Укажите, кто будет выполнять перевозку"
                  : role === "carrier"
                  ? "Укажите заказчика и данные транспорта"
                  : "Укажите заказчика и перевозчика"}
              </div>

              <div className="dual-panel">
                <div className="dual-side">
                  <div className="dual-side-header">
                    <div className="dual-side-dot" style={{ background: "#3b82f6" }} />
                    <div className="dual-side-title">Заказчик</div>
                  </div>
                  {role === "customer" ? (
                    <div>
                      <div className="prefilled-chip">
                        Моя компания
                        <span className="auto-badge">авто</span>
                      </div>
                    </div>
                  ) : (
                    <div className="field-group">
                      <label className="field-label">Заказчик перевозки</label>
                      <div className="search-input-wrap">
                        <span className="search-icon">
                          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
                        </span>
                        <input className="field-input" placeholder="Начните вводить для поиска" />
                      </div>
                    </div>
                  )}
                </div>

                <div className="dual-side">
                  <div className="dual-side-header">
                    <div className="dual-side-dot" style={{ background: "#22c55e" }} />
                    <div className="dual-side-title">Исполнение</div>
                  </div>
                  {role === "carrier" ? (
                    <div>
                      <div className="prefilled-chip" style={{ marginBottom: 16 }}>
                        ИП Астахин Артём Владленович
                        <span className="auto-badge">авто</span>
                      </div>
                      <div className="field-group">
                        <label className="field-label">Водитель</label>
                        <div className="search-input-wrap">
                          <span className="search-icon">
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
                          </span>
                          <input className="field-input" placeholder="Начните вводить для поиска" />
                        </div>
                      </div>
                      <div className="field-group">
                        <label className="field-label">Автомобиль</label>
                        <div className="search-input-wrap">
                          <span className="search-icon">
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
                          </span>
                          <input className="field-input" placeholder="Начните вводить для поиска" />
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="field-group">
                      <label className="field-label">Перевозчик</label>
                      <div className="search-input-wrap">
                        <span className="search-icon">
                          <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
                        </span>
                        <input className="field-input" placeholder="Начните вводить для поиска" />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* STEP 2: Route */}
          {step === 2 && (
            <div>
              <div className="section-title">Маршрут</div>
              <div className="section-desc">
                Укажите адреса погрузки и выгрузки, контактных лиц и время
              </div>

              <div className="route-visual">
                <div className="route-line">
                  <div className="route-dot" />
                  <div className="route-dash" />
                  <div className="route-dot end" />
                </div>
                <div className="route-fields">
                  <div className="route-block">
                    <div className="route-block-title load">Погрузка</div>
                    <div className="field-group">
                      <label className="field-label">Адрес<span className="req">*</span></label>
                      <input className="field-input" placeholder="Город, улица, дом" />
                    </div>
                    <div className="field-row" style={{ marginTop: 8 }}>
                      <div className="field-group">
                        <label className="field-label">Дата и время</label>
                        <input type="datetime-local" className="field-input" />
                      </div>
                      <div className="field-group">
                        <label className="field-label">Тип</label>
                        <select className="field-input field-select">
                          <option value="">Выберите</option>
                          <option>Задняя</option>
                          <option>Боковая</option>
                          <option>Верхняя</option>
                        </select>
                      </div>
                    </div>
                    <div className="field-row" style={{ marginTop: 8 }}>
                      <div className="field-group">
                        <label className="field-label">Отправитель</label>
                        <div className="search-input-wrap">
                          <span className="search-icon">
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
                          </span>
                          <input className="field-input" placeholder="Поиск" />
                        </div>
                      </div>
                      <div className="field-group">
                        <label className="field-label">Контакт</label>
                        <input className="field-input" placeholder="Имя, телефон" />
                      </div>
                    </div>
                  </div>

                  <div className="route-block">
                    <div className="route-block-title unload">Выгрузка</div>
                    <div className="field-group">
                      <label className="field-label">Адрес<span className="req">*</span></label>
                      <input className="field-input" placeholder="Город, улица, дом" />
                    </div>
                    <div className="field-row" style={{ marginTop: 8 }}>
                      <div className="field-group">
                        <label className="field-label">Дата и время</label>
                        <input type="datetime-local" className="field-input" />
                      </div>
                      <div className="field-group">
                        <label className="field-label">Тип</label>
                        <select className="field-input field-select">
                          <option value="">Выберите</option>
                          <option>Задняя</option>
                          <option>Боковая</option>
                          <option>Верхняя</option>
                        </select>
                      </div>
                    </div>
                    <div className="field-row" style={{ marginTop: 8 }}>
                      <div className="field-group">
                        <label className="field-label">Получатель</label>
                        <div className="search-input-wrap">
                          <span className="search-icon">
                            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/></svg>
                          </span>
                          <input className="field-input" placeholder="Поиск" />
                        </div>
                      </div>
                      <div className="field-group">
                        <label className="field-label">Контакт</label>
                        <input className="field-input" placeholder="Имя, телефон" />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* STEP 3: Cargo */}
          {step === 3 && (
            <div>
              <div className="section-title">Груз</div>
              <div className="section-desc">
                Опишите груз и его характеристики
              </div>

              <div className="field-group">
                <label className="field-label">
                  Наименование груза<span className="req">*</span>
                </label>
                <input className="field-input" placeholder="Например: стройматериалы, продукты питания" />
              </div>

              <div className="cargo-specs">
                <div className="spec-card">
                  <label>Вес</label>
                  <input placeholder="—" />
                  <div className="unit">кг</div>
                </div>
                <div className="spec-card">
                  <label>Объём</label>
                  <input placeholder="—" />
                  <div className="unit">м³</div>
                </div>
                <div className="spec-card">
                  <label>Кол-во мест</label>
                  <input placeholder="—" />
                  <div className="unit">шт</div>
                </div>
              </div>

              <div className="field-group" style={{ marginTop: 20 }}>
                <label className="field-label">Комментарий к грузу</label>
                <textarea
                  className="field-input field-textarea"
                  placeholder="Особые условия: температурный режим, хрупкость, опасность..."
                />
              </div>
            </div>
          )}

          {/* STEP 4: Finance */}
          {step === 4 && (
            <div>
              <div className="section-title">Финансы и оплата</div>
              <div className="section-desc">
                {role === "forwarder"
                  ? "Укажите ставки заказчика и перевозчика для расчёта маржи"
                  : role === "customer"
                  ? "Укажите стоимость перевозки — сколько вы платите"
                  : "Укажите стоимость перевозки — сколько вы получите"}
              </div>

              {/* Forwarder: two cards + margin */}
              {role === "forwarder" && (
                <>
                  <div className="finance-card income">
                    <div className="finance-tag income">
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 12V4M4 7l4-4 4 4"/></svg>
                      Заказчик платит нам
                    </div>
                    <div className="finance-amount-row">
                      <input
                        className="finance-amount-input"
                        placeholder="0"
                        value={customerRate}
                        onChange={(e) => setCustomerRate(e.target.value.replace(/\D/g, ""))}
                      />
                      <div className="currency-badge">₽</div>
                    </div>
                    <div className="payment-details">
                      <div className="field-group">
                        <label className="field-label">Форма оплаты</label>
                        <select className="field-input field-select" value={paymentForm} onChange={e => setPaymentForm(e.target.value)}>
                          <option value="">Выберите</option>
                          <option>Безналичная с НДС</option>
                          <option>Безналичная без НДС</option>
                          <option>Наличная</option>
                        </select>
                      </div>
                      <div className="field-group">
                        <label className="field-label">Срок оплаты</label>
                        <div className="radio-group">
                          <label className="radio-pill">
                            <input type="radio" name="pay-term" defaultChecked />
                            <span>{paymentDays} банк. дн.</span>
                          </label>
                          <label className="radio-pill">
                            <input type="radio" name="pay-term" />
                            <span>На выгрузке</span>
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="finance-card expense">
                    <div className="finance-tag expense">
                      <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M8 4v8M4 9l4 4 4-4"/></svg>
                      Мы платим перевозчику
                    </div>
                    <div className="finance-amount-row">
                      <input
                        className="finance-amount-input"
                        placeholder="0"
                        value={carrierRate}
                        onChange={(e) => setCarrierRate(e.target.value.replace(/\D/g, ""))}
                      />
                      <div className="currency-badge">₽</div>
                    </div>
                    <div className="payment-details">
                      <div className="field-group">
                        <label className="field-label">Форма оплаты</label>
                        <select className="field-input field-select" value={paymentFormCarrier} onChange={e => setPaymentFormCarrier(e.target.value)}>
                          <option value="">Выберите</option>
                          <option>Безналичная с НДС</option>
                          <option>Безналичная без НДС</option>
                          <option>Наличная</option>
                        </select>
                      </div>
                      <div className="field-group">
                        <label className="field-label">Срок оплаты</label>
                        <div className="radio-group">
                          <label className="radio-pill">
                            <input type="radio" name="pay-term-c" defaultChecked />
                            <span>{paymentDaysCarrier} банк. дн.</span>
                          </label>
                          <label className="radio-pill">
                            <input type="radio" name="pay-term-c" />
                            <span>На выгрузке</span>
                          </label>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="margin-banner">
                    <div>
                      <div className="margin-label">Маржа</div>
                      <div className="margin-value">
                        {margin !== null
                          ? `${margin.toLocaleString("ru-RU")} ₽`
                          : "— ₽"}
                      </div>
                    </div>
                    {marginPct !== null && (
                      <div className={`margin-pct ${margin > 0 ? "positive" : margin < 0 ? "negative" : "zero"}`}>
                        {margin > 0 ? "+" : ""}{marginPct}%
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* Customer or Carrier: single card */}
              {(role === "customer" || role === "carrier") && (
                <div className="finance-card neutral">
                  <div className="finance-tag neutral">
                    {role === "customer" ? "Стоимость перевозки" : "Стоимость перевозки"}
                  </div>
                  <div className="finance-amount-row">
                    <input
                      className="finance-amount-input"
                      placeholder="0"
                      value={role === "customer" ? carrierRate : customerRate}
                      onChange={(e) => {
                        const v = e.target.value.replace(/\D/g, "");
                        role === "customer" ? setCarrierRate(v) : setCustomerRate(v);
                      }}
                    />
                    <div className="currency-badge">₽</div>
                  </div>
                  <div className="field-hint" style={{ marginBottom: 16 }}>
                    {role === "customer"
                      ? "Сумма, которую вы заплатите за перевозку"
                      : "Сумма, которую вы получите за перевозку"}
                  </div>
                  <div className="payment-details">
                    <div className="field-group">
                      <label className="field-label">Форма оплаты</label>
                      <select className="field-input field-select" value={paymentForm} onChange={e => setPaymentForm(e.target.value)}>
                        <option value="">Выберите</option>
                        <option>Безналичная с НДС</option>
                        <option>Безналичная без НДС</option>
                        <option>Наличная</option>
                      </select>
                    </div>
                    <div className="field-group">
                      <label className="field-label">Срок оплаты</label>
                      <div className="radio-group">
                        <label className="radio-pill">
                          <input type="radio" name="pay-term-s" defaultChecked />
                          <span>5 банк. дн.</span>
                        </label>
                        <label className="radio-pill">
                          <input type="radio" name="pay-term-s" />
                          <span>На выгрузке</span>
                        </label>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {!role && (
                <div style={{ textAlign: "center", padding: "40px 0", color: "#a0a0b4" }}>
                  <div style={{ fontSize: 32, marginBottom: 12 }}>☝️</div>
                  <div style={{ fontSize: 14 }}>
                    Сначала выберите роль на первом шаге
                  </div>
                </div>
              )}

              <div className="field-group" style={{ marginTop: 8 }}>
                <label className="field-label">Комментарии</label>
                <textarea
                  className="field-input field-textarea"
                  placeholder="Дополнительная информация по рейсу..."
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="form-footer">
          <div>
            {step > 0 && (
              <button className="btn btn-secondary" onClick={goPrev}>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M10 3L5 8l5 5"/></svg>
                Назад
              </button>
            )}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button className="btn btn-ghost">Отмена</button>
            {step < STEPS.length - 1 ? (
              <button
                className="btn btn-primary"
                onClick={goNext}
                disabled={step === 0 && !role}
                style={step === 0 && !role ? { opacity: 0.5, pointerEvents: "none" } : {}}
              >
                Далее
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M6 3l5 5-5 5"/></svg>
              </button>
            ) : (
              <button className="btn btn-save">
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8l4 4 6-6"/></svg>
                Сохранить рейс
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
