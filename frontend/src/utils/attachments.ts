import api from '@/utils/api';

/**
 * 聊天附件的前端工具：
 * - 上传（FormData）
 * - 通过带鉴权的请求取回二进制并缓存为 blob URL（<img src> 无法携带 Authorization 头）
 */

export interface UploadedAttachment {
  id: string;
  filename: string;
  kind: 'image' | 'document' | string;
  mime?: string | null;
  size_bytes?: number;
  text_chars?: number;
}

export const IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'];
export const DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.txt', '.md', '.xls', '.xlsx'];

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const MAX_DOCUMENT_BYTES = 30 * 1024 * 1024;

export const extensionOf = (filename: string): string => {
  const idx = (filename || '').lastIndexOf('.');
  return idx >= 0 ? filename.slice(idx).toLowerCase() : '';
};

export const isImageFile = (file: File): boolean => {
  if (file.type?.startsWith('image/')) return true;
  return IMAGE_EXTENSIONS.includes(extensionOf(file.name));
};

export const isSupportedFile = (file: File): boolean => {
  const ext = extensionOf(file.name);
  return isImageFile(file) || DOCUMENT_EXTENSIONS.includes(ext);
};

/** 上传前的本地校验，返回错误提示；通过返回空串。 */
export const validateFile = (file: File): string => {
  if (!isSupportedFile(file)) {
    return `${file.name}：仅支持图片（png/jpg/gif/webp/bmp）和文档（pdf/doc/docx/txt/md/xls/xlsx）`;
  }
  const limit = isImageFile(file) ? MAX_IMAGE_BYTES : MAX_DOCUMENT_BYTES;
  if (file.size > limit) {
    return `${file.name}：文件超过 ${limit / (1024 * 1024)}MB 限制`;
  }
  if (file.size === 0) {
    return `${file.name}：文件内容为空`;
  }
  return '';
};

export const uploadChatAttachment = async (file: File): Promise<UploadedAttachment> => {
  const form = new FormData();
  form.append('file', file);
  const response = await api.post('/chat/attachments', form, {
    // 大文件解析（PDF/Excel）耗时较长，单独放宽超时
    timeout: 120000,
  });
  return response.data as UploadedAttachment;
};

/** 查询后端能力开关：当前模型是否支持图像理解。 */
export const fetchVisionCapability = async (): Promise<boolean> => {
  try {
    const response = await api.get('/chat/capabilities');
    return Boolean(response.data?.vision_enabled);
  } catch (_) {
    return false;
  }
};

const blobUrlCache = new Map<string, string>();
const pendingFetches = new Map<string, Promise<string>>();

/** 取附件的 blob URL（带鉴权），同一附件只请求一次。 */
export const getAttachmentBlobUrl = (attachmentId: string): Promise<string> => {
  const cached = blobUrlCache.get(attachmentId);
  if (cached) return Promise.resolve(cached);
  const pending = pendingFetches.get(attachmentId);
  if (pending) return pending;

  const request = api
    .get(`/chat/attachments/${encodeURIComponent(attachmentId)}/file`, {
      responseType: 'blob',
      timeout: 120000,
    })
    .then((response) => {
      const url = URL.createObjectURL(response.data as Blob);
      blobUrlCache.set(attachmentId, url);
      return url;
    })
    .finally(() => {
      pendingFetches.delete(attachmentId);
    });

  pendingFetches.set(attachmentId, request);
  return request;
};

/** 触发浏览器下载附件；失败时抛出异常由调用方提示。 */
export const downloadAttachment = async (attachmentId: string, filename: string): Promise<void> => {
  const url = await getAttachmentBlobUrl(attachmentId);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename || '附件';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
};
