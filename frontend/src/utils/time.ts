/**
 * 东八区（UTC+8 / Asia/Shanghai）时间格式化工具。
 *
 * 项目全局约定：所有时间统一以东八区为基准时区显示与换算，无论用户浏览器/服务器
 * 处于哪个时区都保持一致。后端输出的时间字符串均带 `+08:00` 偏移（ISO 8601），
 * 本模块使用 `Intl.DateTimeFormat` 配合 `timeZone: 'Asia/Shanghai'` 显式按东八区格式化，
 * 因此即便字符串被解析为绝对时刻，呈现出来的也一定是北京时间。
 */

const TZ = 'Asia/Shanghai';

function parse(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d;
}

const dateTimeFmt = new Intl.DateTimeFormat('zh-CN', {
  timeZone: TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

const dateTimeSecFmt = new Intl.DateTimeFormat('zh-CN', {
  timeZone: TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

const dateFmt = new Intl.DateTimeFormat('zh-CN', {
  timeZone: TZ,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});

const timeFmt = new Intl.DateTimeFormat('zh-CN', {
  timeZone: TZ,
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
});

const timeNoSecFmt = new Intl.DateTimeFormat('zh-CN', {
  timeZone: TZ,
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});

// zh-CN 的 Intl 输出形如 "2024/01/01 10:00:00"，统一规范为 "2024-01-01 10:00:00"。
function normalize(value: string): string {
  return value.replace(/\//g, '-');
}

/** 东八区日期时间（YYYY-MM-DD HH:mm 或带秒）。 */
export function formatUtc8(
  iso: string | null | undefined,
  opts?: { withSeconds?: boolean },
): string {
  const d = parse(iso);
  if (!d) return '';
  return normalize((opts?.withSeconds ? dateTimeSecFmt : dateTimeFmt).format(d));
}

/** 东八区日期（YYYY-MM-DD）。 */
export function formatUtc8Date(iso: string | null | undefined): string {
  const d = parse(iso);
  if (!d) return '';
  return normalize(dateFmt.format(d));
}

/** 东八区时间（HH:mm:ss 或 HH:mm）。 */
export function formatUtc8Time(
  iso: string | null | undefined,
  opts?: { withSeconds?: boolean },
): string {
  const d = parse(iso);
  if (!d) return '';
  return normalize((opts?.withSeconds ? timeFmt : timeNoSecFmt).format(d));
}

/**
 * 智能展示：与当前东八区日期相同则只显示时间（HH:mm），否则显示日期（YYYY-MM-DD）。
 * 用于会话列表等相对时间展示场景。
 */
export function formatUtc8Smart(iso: string | null | undefined): string {
  const d = parse(iso);
  if (!d) return '';
  const now = new Date();
  if (normalize(dateFmt.format(d)) === normalize(dateFmt.format(now))) {
    return formatUtc8Time(iso);
  }
  return formatUtc8Date(iso);
}

/** 生成当前东八区时间字符串（带 +08:00 偏移），用于前端乐观更新时的本地时间戳。 */
export function nowUtc8Iso(): string {
  const d = new Date();
  // 把本地此刻的绝对时刻换算到东八区墙钟，再输出 ISO。
  const utc8 = new Date(d.getTime() + (d.getTimezoneOffset() * 60000) + 8 * 3600000);
  return utc8.toISOString().replace('Z', '+08:00');
}
