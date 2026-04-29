import { useState, useEffect, useCallback, useRef } from 'react';
import {
  AppRoot,
  List,
  Section,
  Cell,
  Button,
  Spinner,
  Placeholder,
  Slider,
  SegmentedControl,
  Text,
} from '@telegram-apps/telegram-ui';

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */
interface RequestData {
  id: number;
  min_hours: number;
  max_hours: number;
  target_date: string | null;
  created_at: string | null;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */
const tg = window.Telegram.WebApp;

const HOURS_MIN = 1.0;
const HOURS_MAX = 10.0;
const STEP = 0.5;

const today = new Date();
const todayISO =
  today.getFullYear() +
  '-' +
  String(today.getMonth() + 1).padStart(2, '0') +
  '-' +
  String(today.getDate()).padStart(2, '0');

function fmtH(v: number): string {
  return (v % 1 === 0 ? v.toFixed(0) : v.toFixed(1)) + 'ч';
}

function formatDate(iso: string): string {
  const p = iso.split('-');
  return p[2] + '.' + p[1] + '.' + p[0];
}

function clamp(v: number, lo: number, hi: number) {
  return Math.max(lo, Math.min(hi, v));
}

function round05(v: number) {
  return Math.round(v / STEP) * STEP;
}

async function api<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: {
      Authorization: 'tma ' + tg.initData,
      'Content-Type': 'application/json',
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch('/api' + path, opts);
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Error');
  return data as T;
}

/* ------------------------------------------------------------------ */
/*  App                                                                */
/* ------------------------------------------------------------------ */
export default function App() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [currentRequest, setCurrentRequest] = useState<RequestData | null>(null);
  const [isEditing, setIsEditing] = useState(false);

  // Form state
  const [dateMode, setDateMode] = useState<'today' | 'date'>('today');
  const [hoursMode, setHoursMode] = useState<'single' | 'range'>('range');
  const [singleHours, setSingleHours] = useState(2.0);
  const [minHours, setMinHours] = useState(2.0);
  const [maxHours, setMaxHours] = useState(3.0);
  const [targetDate, setTargetDate] = useState('');

  const mainButtonCbRef = useRef<(() => void) | null>(null);
  const backButtonCbRef = useRef<(() => void) | null>(null);

  /* ---- Initial load ---- */
  useEffect(() => {
    tg.ready();
    tg.expand();

    if (!tg.initData) {
      setError('Откройте приложение через Telegram.');
      setLoading(false);
      return;
    }

    // Verify the app was opened via the pinned-message button (startapp secret)
    const startParam = new URLSearchParams(window.location.search).get('tgWebAppStartParam');
    if (!startParam) {
      setError('Откройте приложение через кнопку в чате.');
      setLoading(false);
      return;
    }

    api<{ request: RequestData | null }>('GET', '/request')
      .then((data) => {
        setCurrentRequest(data.request);
        setLoading(false);
      })
      .catch((err) => {
        setError('Ошибка загрузки: ' + err.message);
        setLoading(false);
      });
  }, []);

  /* ---- Save ---- */
  const save = useCallback(() => {
    const mh = hoursMode === 'single' ? singleHours : minHours;
    const xh = hoursMode === 'single' ? singleHours : maxHours;
    const dt = dateMode === 'date' ? targetDate : null;

    if (dateMode === 'date' && !dt) {
      tg.showAlert('Выберите дату');
      return;
    }

    tg.MainButton.showProgress(false);
    tg.MainButton.disable();

    api('POST', '/request', { min_hours: mh, max_hours: xh, target_date: dt })
      .then(() => {
        try { tg.HapticFeedback.notificationOccurred('success'); } catch (_) { /* */ }
        tg.close();
      })
      .catch((err: Error) => {
        tg.MainButton.hideProgress();
        tg.MainButton.enable();
        tg.showAlert('Ошибка: ' + err.message);
      });
  }, [hoursMode, singleHours, minHours, maxHours, dateMode, targetDate]);

  /* ---- Cancel ---- */
  const cancelRequest = useCallback(() => {
    tg.showConfirm('Отменить запрос?', (confirmed) => {
      if (!confirmed) return;
      api('DELETE', '/request')
        .then(() => {
          try { tg.HapticFeedback.notificationOccurred('success'); } catch (_) { /* */ }
          tg.close();
        })
        .catch((err: Error) => {
          tg.showAlert('Ошибка: ' + err.message);
        });
    });
  }, []);

  /* ---- Edit button ---- */
  const startEditing = useCallback(() => {
    if (currentRequest) {
      const d = currentRequest.target_date;
      if (d && d > todayISO) {
        setDateMode('date');
        setTargetDate(d);
      } else {
        setDateMode('today');
      }
      if (currentRequest.min_hours === currentRequest.max_hours) {
        setHoursMode('single');
        setSingleHours(currentRequest.min_hours);
      } else {
        setHoursMode('range');
        setMinHours(currentRequest.min_hours);
        setMaxHours(currentRequest.max_hours);
      }
    }
    setIsEditing(true);
    try { tg.HapticFeedback.impactOccurred('light'); } catch (_) { /* */ }
  }, [currentRequest]);

  /* ---- Telegram MainButton / BackButton wiring ---- */
  const showingForm = !loading && !error && (!currentRequest || isEditing);
  const showingView = !loading && !error && !!currentRequest && !isEditing;

  useEffect(() => {
    // Clean previous listeners
    if (mainButtonCbRef.current) tg.MainButton.offClick(mainButtonCbRef.current);
    if (backButtonCbRef.current) tg.BackButton.offClick(backButtonCbRef.current);

    if (showingForm) {
      tg.MainButton.setText(currentRequest ? 'Сохранить' : 'Создать запрос');
      tg.MainButton.show();
      mainButtonCbRef.current = save;
      tg.MainButton.onClick(save);

      if (currentRequest) {
        tg.BackButton.show();
        const goBack = () => setIsEditing(false);
        backButtonCbRef.current = goBack;
        tg.BackButton.onClick(goBack);
      } else {
        tg.BackButton.hide();
        backButtonCbRef.current = null;
      }
    } else {
      tg.MainButton.hide();
      tg.BackButton.hide();
      mainButtonCbRef.current = null;
      backButtonCbRef.current = null;
    }

    return () => {
      if (mainButtonCbRef.current) tg.MainButton.offClick(mainButtonCbRef.current);
      if (backButtonCbRef.current) tg.BackButton.offClick(backButtonCbRef.current);
    };
  }, [showingForm, showingView, currentRequest, save]);

  /* ---- Haptic helper ---- */
  const hapticSelection = () => {
    try { tg.HapticFeedback.selectionChanged(); } catch (_) { /* */ }
  };

  /* ---------------------------------------------------------------- */
  /*  Render                                                           */
  /* ---------------------------------------------------------------- */
  const appearance = tg.colorScheme === 'dark' ? 'dark' : 'light';

  if (loading) {
    return (
      <AppRoot appearance={appearance}>
        <Placeholder>
          <Spinner size="m" />
        </Placeholder>
      </AppRoot>
    );
  }

  if (error) {
    return (
      <AppRoot appearance={appearance}>
        <Placeholder description={error} />
      </AppRoot>
    );
  }

  /* ---------- View mode ---------- */
  if (currentRequest && !isEditing) {
    const d = currentRequest.target_date;
    const dateText = d && d > todayISO ? formatDate(d) : 'Сразу';
    const hoursText =
      currentRequest.min_hours === currentRequest.max_hours
        ? fmtH(currentRequest.min_hours)
        : fmtH(currentRequest.min_hours) + ' – ' + fmtH(currentRequest.max_hours);

    return (
      <AppRoot appearance={appearance}>
        <List>
          <Section header="Ваш запрос">
            <Cell subtitle={dateText}>📅 Дата</Cell>
            <Cell subtitle={hoursText}>⏱ Часы</Cell>
          </Section>

          <div style={{ padding: '0 16px' }}>
            <Button
              size="l"
              stretched
              onClick={startEditing}
              style={{ marginBottom: 10 }}
            >
              ✏️ Редактировать
            </Button>
            <Button
              size="l"
              stretched
              mode="outline"
              onClick={cancelRequest}
              style={{ color: 'var(--tgui--destructive_text_color)' }}
            >
              Отменить запрос
            </Button>
          </div>
        </List>
      </AppRoot>
    );
  }

  /* ---------- Form mode ---------- */
  return (
    <AppRoot appearance={appearance}>
      <List>
        {/* Date section */}
        <Section header="📅 Дата">
          <div style={{ padding: '12px 16px' }}>
            <SegmentedControl>
              <SegmentedControl.Item
                selected={dateMode === 'today'}
                onClick={() => {
                  setDateMode('today');
                  hapticSelection();
                }}
              >
                Сразу
              </SegmentedControl.Item>
              <SegmentedControl.Item
                selected={dateMode === 'date'}
                onClick={() => {
                  setDateMode('date');
                  if (!targetDate) setTargetDate(todayISO);
                  hapticSelection();
                }}
              >
                Дата
              </SegmentedControl.Item>
            </SegmentedControl>
          </div>
          {dateMode === 'date' && (
            <div style={{ padding: '0 16px 12px' }}>
              <input
                type="date"
                min={todayISO}
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                style={{
                  width: '100%',
                  padding: '12px',
                  border: '1px solid var(--tgui--outline)',
                  borderRadius: 12,
                  background: 'var(--tgui--secondary_bg_color, var(--tgui--bg_color))',
                  color: 'var(--tgui--text_color)',
                  fontSize: 17,
                  outline: 'none',
                  boxSizing: 'border-box' as const,
                }}
              />
            </div>
          )}
        </Section>

        {/* Hours mode section */}
        <Section header="⏱ Часы">
          <div style={{ padding: '12px 16px' }}>
            <SegmentedControl>
              <SegmentedControl.Item
                selected={hoursMode === 'single'}
                onClick={() => {
                  setHoursMode('single');
                  setSingleHours(round05(clamp(minHours, HOURS_MIN, HOURS_MAX)));
                  hapticSelection();
                }}
              >
                Точное
              </SegmentedControl.Item>
              <SegmentedControl.Item
                selected={hoursMode === 'range'}
                onClick={() => {
                  setHoursMode('range');
                  setMinHours(singleHours);
                  let mx = round05(clamp(singleHours + 1.0, singleHours, HOURS_MAX));
                  if (mx <= singleHours) mx = round05(clamp(singleHours + 0.5, HOURS_MIN, HOURS_MAX));
                  setMaxHours(mx);
                  hapticSelection();
                }}
              >
                Диапазон
              </SegmentedControl.Item>
            </SegmentedControl>
          </div>
        </Section>

        {/* Slider section */}
        {hoursMode === 'single' ? (
          <Section>
            <div style={{ textAlign: 'center', padding: '16px 0 0' }}>
              <Text style={{ fontSize: 32, fontWeight: 600 }}>{fmtH(singleHours)}</Text>
            </div>
            <Slider
              min={HOURS_MIN}
              max={HOURS_MAX}
              step={STEP}
              value={singleHours}
              onChange={(val) => {
                setSingleHours(val as number);
                hapticSelection();
              }}
            />
          </Section>
        ) : (
          <Section>
            <div style={{ textAlign: 'center', padding: '16px 0 0' }}>
              <Text style={{ fontSize: 32, fontWeight: 600 }}>
                {fmtH(minHours)} – {fmtH(maxHours)}
              </Text>
            </div>
            <Slider
              multiple
              min={HOURS_MIN}
              max={HOURS_MAX}
              step={STEP}
              value={[minHours, maxHours]}
              onChange={(val) => {
                const [lo, hi] = val as [number, number];
                setMinHours(lo);
                setMaxHours(hi);
                hapticSelection();
              }}
            />
          </Section>
        )}
      </List>
    </AppRoot>
  );
}
