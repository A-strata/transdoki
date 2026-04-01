import { useState } from "react";

const T = {
  LOAD: { label: "Погрузка", color: "#16a34a", bg: "#f0fdf4", border: "#bbf7d0", orgLabel: "Отправитель" },
  UNLOAD: { label: "Выгрузка", color: "#dc2626", bg: "#fef2f2", border: "#fecaca", orgLabel: "Получатель" },
};

const empty = (type, id) => ({ id, type, address: "", org: "", date: "", loadType: "", contactName: "", contactPhone: "", expanded: true });

const DEMO = [
  { id: 1, type: "LOAD", address: "Москва, ул. Складская 12, стр. 3", org: "ООО «ТехноГрупп»", loadType: "rear", date: "2026-04-02T08:00", contactName: "Иванов А.В.", contactPhone: "+7 916 123-45-67", expanded: false },
  { id: 2, type: "LOAD", address: "Москва, Промзона Северная, д. 8", org: "ИП Козлов", loadType: "side", date: "2026-04-02T11:00", contactName: "Козлов С.П.", contactPhone: "+7 925 999-88-77", expanded: false },
  { id: 3, type: "UNLOAD", address: "Санкт-Петербург, Софийская ул. 44, к. 2", org: "ООО «НеваЛогистик»", loadType: "rear", date: "2026-04-03T14:00", contactName: "Петров И.Н.", contactPhone: "+7 812 555-44-33", expanded: false },
];

const LOAD_LABELS = { rear: "Задняя", top: "Верхняя", side: "Боковая" };

const SearchIcon = () => (
  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5" /><path d="M10.5 10.5L14 14" /></svg>
);

export default function RouteBuilder() {
  const [points, setPoints] = useState(DEMO);

  const toggle = (id) => setPoints(ps => ps.map(p => p.id === id ? { ...p, expanded: !p.expanded } : p));
  const remove = (id) => setPoints(ps => ps.filter(p => p.id !== id));
  const update = (id, f, v) => setPoints(ps => ps.map(p => p.id === id ? { ...p, [f]: v } : p));
  const add = (type) => setPoints(ps => [...ps, empty(type, Date.now())]);
  const move = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= points.length) return;
    setPoints(ps => { const n = [...ps]; [n[i], n[j]] = [n[j], n[i]]; return n; });
  };

  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Onest:wght@300;400;500;600;700&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        .rb { font-family: 'Onest', system-ui, sans-serif; color: #1a1a2e; max-width: 680px; padding: 24px 0; -webkit-font-smoothing: antialiased; }
        .rb-head { display: flex; align-items: baseline; gap: 10px; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid #f0f0f4; }
        .rb-title { font-size: 15px; font-weight: 600; }
        .rb-desc { font-size: 12px; color: #9494a8; }
        .tl { position: relative; padding-left: 28px; }
        .pt { position: relative; margin-bottom: 8px; }
        .pt:not(:last-child)::after { content: ''; position: absolute; left: -20px; top: 22px; bottom: -20px; width: 2px; background: repeating-linear-gradient(to bottom, #d8d8e4 0, #d8d8e4 4px, transparent 4px, transparent 8px); }
        .pt-dot { position: absolute; left: -24px; top: 12px; width: 10px; height: 10px; border-radius: 50%; border: 2.5px solid; background: #fff; z-index: 2; }
        .pt-card { border: 1px solid #ebebf0; border-radius: 10px; overflow: hidden; transition: all 0.2s; }
        .pt-card:hover { border-color: #d0d0dd; }
        .pt-row { display: flex; align-items: center; gap: 0; min-height: 44px; cursor: pointer; user-select: none; }
        .pt-tag { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 3px 8px; border-radius: 4px; white-space: nowrap; margin: 0 10px; flex-shrink: 0; width: 72px; text-align: center; }
        .pt-addr { flex: 1; font-size: 13px; font-weight: 500; color: #1a1a2e; padding: 0 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .pt-addr.empty { color: #c0c0cc; font-weight: 400; }
        .pt-meta { display: flex; align-items: center; gap: 6px; padding-right: 6px; flex-shrink: 0; }
        .pt-chip { font-size: 11px; color: #8b8b9e; background: #f4f4f8; padding: 2px 8px; border-radius: 4px; white-space: nowrap; }
        .pt-actions { display: flex; gap: 2px; margin-right: 4px; }
        .pt-actions button { width: 24px; height: 24px; border: none; background: none; cursor: pointer; color: #b0b0c0; border-radius: 4px; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }
        .pt-actions button:hover { background: #f4f4f8; color: #5a5a70; }
        .pt-del:hover { background: #fef2f2 !important; color: #dc2626 !important; }
        .pt-chev { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; color: #b0b0c0; transition: transform 0.2s; flex-shrink: 0; }
        .pt-chev.open { transform: rotate(180deg); }
        .pt-detail { padding: 0 14px 14px; border-top: 1px solid #f4f4f8; animation: sd 0.2s ease; }
        @keyframes sd { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .gr3 { display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 8px 12px; margin-top: 10px; }
        .gr3e { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px 12px; margin-top: 8px; }
        .fg {}
        .fl { display: block; font-size: 11px; font-weight: 500; color: #8b8b9e; margin-bottom: 3px; }
        .fl .req { color: #e74c3c; margin-left: 2px; }
        .fi { width: 100%; height: 34px; border: 1.5px solid #e0e0ea; border-radius: 7px; padding: 0 10px; font-size: 12px; font-family: inherit; color: #1a1a2e; background: #fff; outline: none; transition: all 0.15s; }
        .fi:hover { border-color: #c8c8d8; }
        .fi:focus { border-color: #3366ff; box-shadow: 0 0 0 3px rgba(51,102,255,0.08); }
        .fi::placeholder { color: #c8c8d4; }
        .fi-sel { appearance: none; background-image: url("data:image/svg+xml,%3Csvg width='10' height='6' viewBox='0 0 10 6' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1l4 4 4-4' stroke='%239494a8' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 10px center; padding-right: 28px; }
        .si { position: relative; }
        .si .fi { padding-left: 30px; }
        .si-icon { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: #c0c0cc; display: flex; }
        .add-row { display: flex; gap: 8px; margin-top: 4px; }
        .add-btn { display: flex; align-items: center; gap: 6px; height: 36px; padding: 0 14px; border: 1.5px dashed #d8d8e4; border-radius: 8px; background: none; cursor: pointer; font-size: 12px; font-weight: 500; font-family: inherit; color: #8b8b9e; transition: all 0.15s; }
        .add-btn:hover { border-color: #b0b0c4; color: #5a5a70; background: #fafafd; }
      `}</style>

      <div className="rb">
        <div className="rb-head">
          <div className="rb-title">Маршрут</div>
          <div className="rb-desc">Точки погрузки и выгрузки по порядку следования</div>
        </div>

        <div className="tl">
          {points.map((pt, idx) => {
            const cfg = T[pt.type];
            const ex = pt.expanded;
            return (
              <div className="pt" key={pt.id}>
                <div className="pt-dot" style={{ borderColor: cfg.color }} />
                <div className="pt-card" style={ex ? { borderColor: cfg.border, background: cfg.bg } : {}}>

                  <div className="pt-row" onClick={() => toggle(pt.id)}>
                    <div className="pt-tag" style={{ background: cfg.bg, color: cfg.color }}>{cfg.label}</div>
                    <div className={`pt-addr ${!pt.address ? "empty" : ""}`}>
                      {pt.address || "Укажите адрес"}
                    </div>
                    <div className="pt-meta">
                      {pt.date && <span className="pt-chip">{new Date(pt.date).toLocaleDateString("ru-RU", { day: "numeric", month: "short" })}</span>}
                      {pt.loadType && <span className="pt-chip">{LOAD_LABELS[pt.loadType] || pt.loadType}</span>}
                    </div>
                    <div className="pt-actions" onClick={e => e.stopPropagation()}>
                      <button onClick={() => move(idx, -1)} title="Вверх" style={idx === 0 ? { opacity: 0.3, pointerEvents: "none" } : {}}>
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M6 9V3M3.5 5.5L6 3l2.5 2.5" /></svg>
                      </button>
                      <button onClick={() => move(idx, 1)} title="Вниз" style={idx === points.length - 1 ? { opacity: 0.3, pointerEvents: "none" } : {}}>
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M6 3v6M3.5 6.5L6 9l2.5-2.5" /></svg>
                      </button>
                      {points.length > 2 && (
                        <button className="pt-del" onClick={() => remove(pt.id)} title="Удалить">
                          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2.5 3h7M4.5 3V2.5a1 1 0 011-1h1a1 1 0 011 1V3M9 3v6.5a1 1 0 01-1 1H4a1 1 0 01-1-1V3" /></svg>
                        </button>
                      )}
                    </div>
                    <div className={`pt-chev ${ex ? "open" : ""}`}>
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M3 4.5L6 7.5 9 4.5" /></svg>
                    </div>
                  </div>

                  {ex && (
                    <div className="pt-detail">
                      <div className="gr3">
                        <div className="fg">
                          <label className="fl">Адрес<span className="req">*</span></label>
                          <input className="fi" value={pt.address} onChange={e => update(pt.id, "address", e.target.value)} placeholder="Город, улица, дом" />
                        </div>
                        <div className="fg">
                          <label className="fl">Дата и время<span className="req">*</span></label>
                          <input type="datetime-local" className="fi" value={pt.date} onChange={e => update(pt.id, "date", e.target.value)} />
                        </div>
                        <div className="fg">
                          <label className="fl">Тип погрузки</label>
                          <select className="fi fi-sel" value={pt.loadType} onChange={e => update(pt.id, "loadType", e.target.value)}>
                            <option value="">—</option>
                            <option value="rear">Задняя</option>
                            <option value="side">Боковая</option>
                            <option value="top">Верхняя</option>
                          </select>
                        </div>
                      </div>
                      <div className="gr3e">
                        <div className="fg">
                          <label className="fl">{cfg.orgLabel}</label>
                          <div className="si">
                            <span className="si-icon"><SearchIcon /></span>
                            <input className="fi" value={pt.org} onChange={e => update(pt.id, "org", e.target.value)} placeholder="Поиск по названию или ИНН" />
                          </div>
                        </div>
                        <div className="fg">
                          <label className="fl">Контакт (имя)</label>
                          <input className="fi" value={pt.contactName} onChange={e => update(pt.id, "contactName", e.target.value)} placeholder="ФИО" />
                        </div>
                        <div className="fg">
                          <label className="fl">Контакт (телефон)</label>
                          <input className="fi" value={pt.contactPhone} onChange={e => update(pt.id, "contactPhone", e.target.value)} placeholder="+7 ___  ___-__-__" />
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="add-row">
          <button className="add-btn" onClick={() => add("LOAD")}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#16a34a" strokeWidth="1.5"><path d="M7 3v8M3 7h8" /></svg>
            Погрузка
          </button>
          <button className="add-btn" onClick={() => add("UNLOAD")}>
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" stroke="#dc2626" strokeWidth="1.5"><path d="M7 3v8M3 7h8" /></svg>
            Выгрузка
          </button>
        </div>
      </div>
    </>
  );
}
