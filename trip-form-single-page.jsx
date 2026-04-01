import { useState, useEffect, useRef, useCallback } from "react";

const SECTIONS = [
  { id: "role", label: "Роль" },
  { id: "participants", label: "Участники" },
  { id: "route", label: "Маршрут" },
  { id: "cargo", label: "Груз" },
  { id: "finance", label: "Финансы" },
];

const ROLES = [
  {
    id: "customer",
    title: "Заказчик",
    desc: "Моя фирма заказывает перевозку",
    icon: (
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
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
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
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
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <path d="M12 6v6l4 2" />
      </svg>
    ),
  },
];

export default function TripFormSinglePage() {
  const [role, setRole] = useState("carrier");
  const [activeSection, setActiveSection] = useState("role");
  const [customerRate, setCustomerRate] = useState("");
  const [carrierRate, setCarrierRate] = useState("");
  const sectionRefs = useRef({});
  const navRef = useRef(null);
  const containerRef = useRef(null);

  const registerRef = useCallback((id, el) => {
    if (el) sectionRefs.current[id] = el;
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const onScroll = () => {
      const navH = navRef.current ? navRef.current.offsetHeight + 16 : 60;
      const scrollTop = container.scrollTop;
      let current = "role";
      for (const s of SECTIONS) {
        const el = sectionRefs.current[s.id];
        if (el && el.offsetTop - navH - 24 <= scrollTop) current = s.id;
      }
      setActiveSection(current);
    };
    container.addEventListener("scroll", onScroll, { passive: true });
    return () => container.removeEventListener("scroll", onScroll);
  }, []);

  const scrollTo = (id) => {
    const el = sectionRefs.current[id];
    const container = containerRef.current;
    const navH = navRef.current ? navRef.current.offsetHeight : 52;
    if (el && container) {
      container.scrollTo({ top: el.offsetTop - navH - 20, behavior: "smooth" });
    }
  };

  const margin = customerRate && carrierRate ? Number(customerRate) - Number(carrierRate) : null;
  const marginPct = margin !== null && Number(customerRate) > 0 ? Math.round((margin / Number(customerRate)) * 100) : null;

  const formatNum = (v) => v ? Number(v).toLocaleString("ru-RU") : "";

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Onest:wght@300;400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }

        .tf { font-family: 'Onest', system-ui, sans-serif; color: #1a1a2e; -webkit-font-smoothing: antialiased; height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

        /* Sticky nav */
        .tf-nav { display: flex; align-items: center; gap: 2px; padding: 10px 32px; border-bottom: 1px solid #ebebf0; background: #fff; flex-shrink: 0; z-index: 10; }
        .tf-nav-item { padding: 6px 14px; font-size: 12px; font-weight: 500; color: #9494a8; border-radius: 6px; cursor: pointer; border: none; background: none; font-family: inherit; transition: all 0.2s; letter-spacing: 0.2px; }
        .tf-nav-item:hover { color: #4a4a60; background: #f4f4f8; }
        .tf-nav-item.active { color: #3366ff; background: #eef2ff; }
        .tf-nav-title { font-size: 15px; font-weight: 600; margin-right: 16px; color: #1a1a2e; white-space: nowrap; }
        .tf-nav-spacer { flex: 1; }
        .tf-nav .btn-save { height: 34px; padding: 0 20px; border-radius: 8px; font-size: 13px; font-weight: 600; font-family: inherit; cursor: pointer; border: none; background: #1a1a2e; color: #fff; transition: all 0.15s; display: flex; align-items: center; gap: 6px; }
        .tf-nav .btn-save:hover { background: #2d2d4e; }
        .tf-nav .btn-cancel { height: 34px; padding: 0 16px; border-radius: 8px; font-size: 13px; font-weight: 500; font-family: inherit; cursor: pointer; border: 1px solid #e0e0ea; background: #fff; color: #8b8b9e; margin-right: 6px; transition: all 0.15s; }
        .tf-nav .btn-cancel:hover { background: #f8f8fb; color: #4a4a60; }

        /* Scroll area */
        .tf-scroll { flex: 1; overflow-y: auto; padding: 28px 32px 80px; }

        /* Sections */
        .section { margin-bottom: 40px; }
        .section-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 18px; padding-bottom: 10px; border-bottom: 1px solid #f0f0f4; }
        .section-title { font-size: 15px; font-weight: 600; color: #1a1a2e; letter-spacing: -0.2px; }
        .section-desc { font-size: 12px; color: #9494a8; }

        /* Role cards */
        .role-row { display: flex; gap: 10px; margin-bottom: 18px; }
        .role-card { flex: 1; display: flex; align-items: center; gap: 12px; padding: 12px 16px; border: 1.5px solid #e8e8ee; border-radius: 10px; cursor: pointer; background: #fff; transition: all 0.2s; }
        .role-card:hover { border-color: #c8c8d8; }
        .role-card.sel { border-color: #3366ff; background: #f8faff; box-shadow: 0 0 0 3px rgba(51,102,255,0.08); }
        .role-icon { width: 40px; height: 40px; border-radius: 10px; background: #f4f4f8; display: flex; align-items: center; justify-content: center; color: #8b8b9e; transition: all 0.2s; flex-shrink: 0; }
        .role-card.sel .role-icon { background: #3366ff; color: #fff; }
        .role-card h3 { font-size: 13px; font-weight: 600; color: #1a1a2e; margin-bottom: 1px; }
        .role-card p { font-size: 11px; color: #9494a8; line-height: 1.3; }

        /* Fields */
        .fg { margin-bottom: 14px; }
        .fl { display: block; font-size: 12px; font-weight: 500; color: #5a5a70; margin-bottom: 5px; }
        .fl .req { color: #e74c3c; margin-left: 2px; }
        .fi { width: 100%; height: 38px; border: 1.5px solid #e0e0ea; border-radius: 8px; padding: 0 12px; font-size: 13px; font-family: inherit; color: #1a1a2e; background: #fff; transition: all 0.15s; outline: none; }
        .fi:hover { border-color: #c8c8d8; }
        .fi:focus { border-color: #3366ff; box-shadow: 0 0 0 3px rgba(51,102,255,0.08); }
        .fi::placeholder { color: #c0c0cc; }
        .fi-ta { height: 72px; padding: 10px 12px; resize: vertical; }
        .fi-sel { appearance: none; background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%239494a8' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 12px center; padding-right: 32px; }
        .frow { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        .frow3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
        .hint { font-size: 11px; color: #a8a8bc; margin-top: 3px; }

        /* Search input */
        .si { position: relative; }
        .si .fi { padding-left: 32px; }
        .si-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); color: #c0c0cc; }

        /* Auto chip */
        .auto-chip { display: inline-flex; align-items: center; gap: 8px; background: #f0f4ff; border: 1px solid #d0dcf8; border-radius: 8px; padding: 8px 12px; font-size: 13px; color: #1e40af; font-weight: 500; }
        .auto-badge { font-size: 9px; background: #d0dcf8; color: #1d4ed8; padding: 2px 6px; border-radius: 3px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; }
        .auto-field { background: #f8f8fb; border: 1.5px dashed #d8d8e4; border-radius: 8px; padding: 9px 12px; font-size: 12px; color: #a0a0b4; }

        /* Dual panel */
        .dual { display: grid; grid-template-columns: 1fr 1fr; border: 1px solid #ebebf0; border-radius: 10px; overflow: hidden; }
        .dual-side { padding: 18px; }
        .dual-side:first-child { border-right: 1px solid #ebebf0; }
        .dual-dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; margin-right: 7px; }
        .dual-label { font-size: 12px; font-weight: 600; color: #1a1a2e; margin-bottom: 14px; padding-bottom: 10px; border-bottom: 1px solid #f4f4f8; }

        /* Route visual */
        .rv { display: flex; gap: 14px; }
        .rv-line { display: flex; flex-direction: column; align-items: center; padding-top: 8px; width: 18px; flex-shrink: 0; }
        .rv-dot { width: 10px; height: 10px; border-radius: 50%; border: 2.5px solid; flex-shrink: 0; background: #fff; }
        .rv-dot.load { border-color: #22c55e; }
        .rv-dot.unload { border-color: #ef4444; }
        .rv-dash { width: 2px; flex: 1; min-height: 24px; background: repeating-linear-gradient(to bottom, #d8d8e4 0, #d8d8e4 4px, transparent 4px, transparent 8px); }
        .rv-blocks { flex: 1; display: flex; flex-direction: column; gap: 12px; }
        .rv-block { background: #f8f8fb; border-radius: 10px; padding: 14px; }
        .rv-block-title { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
        .rv-block-title.load { color: #16a34a; }
        .rv-block-title.unload { color: #dc2626; }

        /* Cargo specs */
        .specs { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-top: 12px; }
        .spec { background: #f4f4f8; border-radius: 10px; padding: 12px; text-align: center; }
        .spec label { font-size: 10px; color: #8b8b9e; text-transform: uppercase; letter-spacing: 0.4px; font-weight: 600; display: block; margin-bottom: 6px; }
        .spec input { width: 100%; text-align: center; border: 1.5px solid transparent; background: #fff; border-radius: 6px; height: 34px; font-size: 16px; font-weight: 600; font-family: inherit; color: #1a1a2e; outline: none; transition: border-color 0.15s; }
        .spec input:focus { border-color: #3366ff; }
        .spec .unit { font-size: 10px; color: #a8a8bc; margin-top: 3px; }

        /* Finance */
        .fc { border: 1.5px solid #e0e0ea; border-radius: 12px; padding: 18px; margin-bottom: 12px; transition: all 0.3s; }
        .fc.income { border-color: #bbf7d0; background: #f7fdf9; }
        .fc.expense { border-color: #fecaca; background: #fefafa; }
        .fc.neutral { background: #fafafd; }
        .fc-tag { display: inline-flex; align-items: center; gap: 5px; font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4px; padding: 3px 8px; border-radius: 5px; margin-bottom: 12px; }
        .fc-tag.income { background: #dcfce7; color: #15803d; }
        .fc-tag.expense { background: #fee2e2; color: #b91c1c; }
        .fc-tag.neutral { background: #f0f0f8; color: #6b6b80; }
        .fc-amount { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
        .fc-input { flex: 1; height: 44px; border: 1.5px solid #e0e0ea; border-radius: 8px; padding: 0 14px; font-size: 18px; font-weight: 600; font-family: inherit; color: #1a1a2e; background: #fff; outline: none; transition: all 0.15s; }
        .fc-input:focus { border-color: #3366ff; box-shadow: 0 0 0 3px rgba(51,102,255,0.08); }
        .fc-cur { height: 44px; padding: 0 14px; border: 1.5px solid #e0e0ea; border-radius: 8px; background: #f8f8fb; font-size: 14px; font-weight: 600; color: #6b6b80; display: flex; align-items: center; }
        .fc-details { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding-top: 14px; border-top: 1px solid #f0f0f4; }

        /* Radio pills */
        .rpills { display: flex; gap: 6px; }
        .rpill { flex: 1; cursor: pointer; }
        .rpill input { display: none; }
        .rpill span { display: block; text-align: center; padding: 7px 8px; border: 1.5px solid #e0e0ea; border-radius: 6px; font-size: 12px; color: #6b6b80; font-weight: 500; transition: all 0.15s; }
        .rpill input:checked + span { border-color: #3366ff; background: #f0f4ff; color: #3366ff; }

        /* Margin banner */
        .mb { background: #1a1a2e; border-radius: 10px; padding: 14px 18px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px; color: #fff; }
        .mb-label { font-size: 11px; color: rgba(255,255,255,0.5); font-weight: 500; margin-bottom: 2px; }
        .mb-val { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
        .mb-pct { font-size: 13px; font-weight: 600; padding: 3px 10px; border-radius: 6px; background: rgba(255,255,255,0.12); }
        .mb-pct.pos { color: #4ade80; }
        .mb-pct.neg { color: #f87171; }

        /* Transition for role-dependent sections */
        .role-transition { animation: slideIn 0.25s ease; }
        @keyframes slideIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>

      <div className="tf">
        {/* Sticky nav */}
        <div className="tf-nav" ref={navRef}>
          <span className="tf-nav-title">Новый рейс</span>
          {SECTIONS.map((s) => (
            <button key={s.id} className={`tf-nav-item ${activeSection === s.id ? "active" : ""}`} onClick={() => scrollTo(s.id)}>
              {s.label}
            </button>
          ))}
          <span className="tf-nav-spacer" />
          <button className="btn-cancel">Отмена</button>
          <button className="btn-save">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 8l4 4 6-6" /></svg>
            Сохранить
          </button>
        </div>

        {/* Single scrollable area */}
        <div className="tf-scroll" ref={containerRef}>

          {/* ─── ROLE ─── */}
          <div className="section" ref={(el) => registerRef("role", el)}>
            <div className="section-head">
              <div className="section-title">Моя роль в перевозке</div>
              <div className="section-desc">Определит видимость полей ниже</div>
            </div>

            <div className="role-row">
              {ROLES.map((r) => (
                <div key={r.id} className={`role-card ${role === r.id ? "sel" : ""}`} onClick={() => setRole(r.id)}>
                  <div className="role-icon">{r.icon}</div>
                  <div>
                    <h3>{r.title}</h3>
                    <p>{r.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="frow">
              <div className="fg">
                <label className="fl">Номер заявки</label>
                <div className="auto-field">Присвоится автоматически</div>
              </div>
              <div className="fg">
                <label className="fl">Дата заявки<span className="req">*</span></label>
                <input type="date" className="fi" />
              </div>
            </div>
          </div>

          {/* ─── PARTICIPANTS ─── */}
          <div className="section" ref={(el) => registerRef("participants", el)}>
            <div className="section-head">
              <div className="section-title">Участники перевозки</div>
              <div className="section-desc">
                {role === "customer" ? "Укажите исполнителя" : role === "carrier" ? "Укажите заказчика и транспорт" : "Укажите заказчика и перевозчика"}
              </div>
            </div>

            <div className="dual" key={role + "-participants"}>
              <div className="dual-side role-transition">
                <div className="dual-label"><span className="dual-dot" style={{ background: "#3b82f6" }} />Заказчик</div>
                {role === "customer" ? (
                  <div className="auto-chip">Моя компания <span className="auto-badge">авто</span></div>
                ) : (
                  <div className="fg">
                    <label className="fl">Заказчик перевозки</label>
                    <div className="si">
                      <span className="si-icon"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg></span>
                      <input className="fi" placeholder="Поиск по названию или ИНН" />
                    </div>
                  </div>
                )}
              </div>

              <div className="dual-side role-transition">
                <div className="dual-label"><span className="dual-dot" style={{ background: "#22c55e" }} />Исполнение</div>
                {role === "carrier" ? (
                  <>
                    <div className="auto-chip" style={{ marginBottom: 12 }}>ИП Астахин Артём Владленович <span className="auto-badge">авто</span></div>
                    <div className="fg">
                      <label className="fl">Водитель</label>
                      <div className="si">
                        <span className="si-icon"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg></span>
                        <input className="fi" placeholder="Поиск" />
                      </div>
                    </div>
                    <div className="frow">
                      <div className="fg">
                        <label className="fl">Автомобиль</label>
                        <div className="si">
                          <span className="si-icon"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg></span>
                          <input className="fi" placeholder="Поиск" />
                        </div>
                      </div>
                      <div className="fg">
                        <label className="fl">Прицеп</label>
                        <div className="si">
                          <span className="si-icon"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg></span>
                          <input className="fi" placeholder="Поиск" />
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="fg">
                    <label className="fl">Перевозчик</label>
                    <div className="si">
                      <span className="si-icon"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg></span>
                      <input className="fi" placeholder="Поиск по названию или ИНН" />
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* ─── ROUTE ─── */}
          <div className="section" ref={(el) => registerRef("route", el)}>
            <div className="section-head">
              <div className="section-title">Маршрут</div>
              <div className="section-desc">Погрузка и выгрузка</div>
            </div>

            <div className="rv">
              <div className="rv-line">
                <div className="rv-dot load" />
                <div className="rv-dash" />
                <div className="rv-dot unload" />
              </div>
              <div className="rv-blocks">
                {/* Loading */}
                <div className="rv-block">
                  <div className="rv-block-title load">Погрузка</div>
                  <div className="fg">
                    <label className="fl">Адрес<span className="req">*</span></label>
                    <input className="fi" placeholder="Город, улица, дом" />
                  </div>
                  <div className="frow">
                    <div className="fg">
                      <label className="fl">Отправитель</label>
                      <div className="si">
                        <span className="si-icon"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg></span>
                        <input className="fi" placeholder="Поиск" />
                      </div>
                    </div>
                    <div className="fg">
                      <label className="fl">Тип погрузки</label>
                      <select className="fi fi-sel">
                        <option value="">—</option>
                        <option>Задняя</option>
                        <option>Боковая</option>
                        <option>Верхняя</option>
                      </select>
                    </div>
                  </div>
                  <div className="frow">
                    <div className="fg">
                      <label className="fl">Дата и время</label>
                      <input type="datetime-local" className="fi" />
                    </div>
                    <div className="fg">
                      <label className="fl">Контакт на месте</label>
                      <input className="fi" placeholder="Имя, телефон" />
                    </div>
                  </div>
                </div>

                {/* Unloading */}
                <div className="rv-block">
                  <div className="rv-block-title unload">Выгрузка</div>
                  <div className="fg">
                    <label className="fl">Адрес<span className="req">*</span></label>
                    <input className="fi" placeholder="Город, улица, дом" />
                  </div>
                  <div className="frow">
                    <div className="fg">
                      <label className="fl">Получатель</label>
                      <div className="si">
                        <span className="si-icon"><svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg></span>
                        <input className="fi" placeholder="Поиск" />
                      </div>
                    </div>
                    <div className="fg">
                      <label className="fl">Тип выгрузки</label>
                      <select className="fi fi-sel">
                        <option value="">—</option>
                        <option>Задняя</option>
                        <option>Боковая</option>
                        <option>Верхняя</option>
                      </select>
                    </div>
                  </div>
                  <div className="frow">
                    <div className="fg">
                      <label className="fl">Дата и время</label>
                      <input type="datetime-local" className="fi" />
                    </div>
                    <div className="fg">
                      <label className="fl">Контакт на месте</label>
                      <input className="fi" placeholder="Имя, телефон" />
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* ─── CARGO ─── */}
          <div className="section" ref={(el) => registerRef("cargo", el)}>
            <div className="section-head">
              <div className="section-title">Груз</div>
            </div>

            <div className="fg">
              <label className="fl">Наименование<span className="req">*</span></label>
              <input className="fi" placeholder="Стройматериалы, продукты питания, оборудование..." />
            </div>

            <div className="specs">
              <div className="spec">
                <label>Вес</label>
                <input placeholder="—" />
                <div className="unit">кг</div>
              </div>
              <div className="spec">
                <label>Объём</label>
                <input placeholder="—" />
                <div className="unit">м³</div>
              </div>
              <div className="spec">
                <label>Мест</label>
                <input placeholder="—" />
                <div className="unit">шт</div>
              </div>
            </div>
          </div>

          {/* ─── FINANCE ─── */}
          <div className="section" ref={(el) => registerRef("finance", el)}>
            <div className="section-head">
              <div className="section-title">Финансы и оплата</div>
              <div className="section-desc">
                {role === "forwarder" ? "Доход, расход и маржа" : role === "customer" ? "Сколько вы платите" : "Сколько вы получите"}
              </div>
            </div>

            <div key={role + "-finance"} className="role-transition">
              {/* ── Forwarder: two cards + margin ── */}
              {role === "forwarder" && (
                <>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                    <div className="fc income">
                      <div className="fc-tag income">
                        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M8 12V4M5 7l3-3 3 3" /></svg>
                        Заказчик платит нам
                      </div>
                      <div className="fc-amount">
                        <input className="fc-input" placeholder="0" value={customerRate} onChange={(e) => setCustomerRate(e.target.value.replace(/\D/g, ""))} />
                        <div className="fc-cur">₽</div>
                      </div>
                      <div className="fc-details">
                        <div className="fg">
                          <label className="fl">Форма оплаты</label>
                          <select className="fi fi-sel"><option value="">—</option><option>Безнал с НДС</option><option>Безнал без НДС</option><option>Наличные</option></select>
                        </div>
                        <div className="fg">
                          <label className="fl">Срок оплаты</label>
                          <div className="rpills">
                            <label className="rpill"><input type="radio" name="pt1" defaultChecked /><span>5 банк. дн.</span></label>
                            <label className="rpill"><input type="radio" name="pt1" /><span>На выгрузке</span></label>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="fc expense">
                      <div className="fc-tag expense">
                        <svg width="10" height="10" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M8 4v8M5 9l3 3 3-3" /></svg>
                        Мы платим перевозчику
                      </div>
                      <div className="fc-amount">
                        <input className="fc-input" placeholder="0" value={carrierRate} onChange={(e) => setCarrierRate(e.target.value.replace(/\D/g, ""))} />
                        <div className="fc-cur">₽</div>
                      </div>
                      <div className="fc-details">
                        <div className="fg">
                          <label className="fl">Форма оплаты</label>
                          <select className="fi fi-sel"><option value="">—</option><option>Безнал с НДС</option><option>Безнал без НДС</option><option>Наличные</option></select>
                        </div>
                        <div className="fg">
                          <label className="fl">Срок оплаты</label>
                          <div className="rpills">
                            <label className="rpill"><input type="radio" name="pt2" defaultChecked /><span>5 банк. дн.</span></label>
                            <label className="rpill"><input type="radio" name="pt2" /><span>На выгрузке</span></label>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="mb">
                    <div>
                      <div className="mb-label">Маржа</div>
                      <div className="mb-val">{margin !== null ? `${margin.toLocaleString("ru-RU")} ₽` : "— ₽"}</div>
                    </div>
                    {marginPct !== null && (
                      <div className={`mb-pct ${margin > 0 ? "pos" : "neg"}`}>
                        {margin > 0 ? "+" : ""}{marginPct}%
                      </div>
                    )}
                  </div>
                </>
              )}

              {/* ── Customer or Carrier: single card ── */}
              {(role === "customer" || role === "carrier") && (
                <div className="fc neutral">
                  <div className="fc-tag neutral">Стоимость перевозки</div>
                  <div className="fc-amount">
                    <input
                      className="fc-input"
                      placeholder="0"
                      value={role === "customer" ? carrierRate : customerRate}
                      onChange={(e) => {
                        const v = e.target.value.replace(/\D/g, "");
                        role === "customer" ? setCarrierRate(v) : setCustomerRate(v);
                      }}
                    />
                    <div className="fc-cur">₽</div>
                  </div>
                  <div className="hint" style={{ marginBottom: 14 }}>
                    {role === "customer" ? "Сумма, которую вы заплатите за перевозку" : "Сумма, которую вы получите за перевозку"}
                  </div>
                  <div className="fc-details">
                    <div className="fg">
                      <label className="fl">Форма оплаты</label>
                      <select className="fi fi-sel"><option value="">—</option><option>Безнал с НДС</option><option>Безнал без НДС</option><option>Наличные</option></select>
                    </div>
                    <div className="fg">
                      <label className="fl">Срок оплаты</label>
                      <div className="rpills">
                        <label className="rpill"><input type="radio" name="pts" defaultChecked /><span>5 банк. дн.</span></label>
                        <label className="rpill"><input type="radio" name="pts" /><span>На выгрузке</span></label>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="fg" style={{ marginTop: 4 }}>
              <label className="fl">Комментарии</label>
              <textarea className="fi fi-ta" placeholder="Дополнительная информация по рейсу..." />
            </div>
          </div>

        </div>
      </div>
    </>
  );
}
