import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

type Language = "zh" | "en";
type Provider = { id: string; name: string; base_url: string; custom?: boolean };
type PreviewBlock = { block_id: string; tag: string; text: string };
type Failure = { id: string; text_snippet: string; reason: string };
type JobStatus = {
  status: string;
  progress: number;
  processed_blocks: number;
  pending_blocks: number;
  counts: {
    total: number;
    cache_hits: number;
    misses: number;
    translated: number;
    placeholders: number;
    failures: number;
  };
  failures: Failure[];
  output_name?: string;
  can_download: boolean;
  target_language: string;
};
type AppConfig = {
  providers: Provider[];
  target_languages: string[];
  defaults: {
    model: string;
    temperature: number;
    batch_size: number;
    concurrency: number;
    max_blocks: number;
    target_language: string;
  };
};

const LANGUAGE_STORAGE_KEY = "epub-bilingual-ui-language";

const emptyJob: JobStatus = {
  status: "idle",
  progress: 0,
  processed_blocks: 0,
  pending_blocks: 0,
  counts: {
    total: 0,
    cache_hits: 0,
    misses: 0,
    translated: 0,
    placeholders: 0,
    failures: 0
  },
  failures: [],
  can_download: false,
  target_language: "Chinese"
};

const text = {
  zh: {
    localPress: "local bilingual press",
    appTitle: "EPUB 行间双语翻译器",
    heroCopy: "把一本书慢慢拆成段落、缓存、译文和纸面秩序。",
    language: "Language",
    manuscript: "Manuscript",
    manuscriptTitle: "书稿与流程",
    chooseEpub: "选择一本 EPUB",
    uploadHint: "上传后可先解析预览，再开始翻译。",
    parsePreview: "解析预览",
    startTranslation: "开始翻译",
    restartTranslation: "重新开始翻译",
    progress: "Progress",
    progressTitle: "翻译状态",
    pause: "暂停",
    resume: "继续",
    clear: "清空",
    totalBlocks: "总文本块",
    processed: "已处理",
    cacheHits: "缓存命中",
    failed: "失败",
    pending: "剩余",
    status: "状态",
    download: "下载",
    bilingualEpub: "双语 EPUB",
    failures: "失败段落",
    retryFailures: "重试失败段落",
    preview: "Preview",
    previewTitle: "解析预览",
    blockUnit: "个文本块",
    settings: "Settings",
    settingsTitle: "译者配置",
    provider: "Provider",
    apiKey: "API Key",
    baseUrl: "Base URL",
    model: "Model",
    fetchModels: "获取模型",
    testConnection: "测试连接",
    targetLanguage: "目标语言",
    custom: "自定义",
    customTargetLanguage: "自定义目标语言",
    temperature: "温度",
    batchSize: "批大小",
    concurrency: "并发",
    maxBlocks: "最大块",
    stylePrompt: "风格提示",
    promptPlaceholder: "例如：译文温柔、克制，保留文学节奏。",
    glossary: "全局术语表",
    glossaryPlaceholder: "例如：\nAlice=爱丽丝\nKing's Landing=君临城",
    debug: "调试与连接详情",
    noConnection: "暂无连接测试结果",
    clearCache: "清除翻译缓存",
    cacheCleared: "已清除 {count} 条缓存。",
    extractGlossary: "自动提取术语",
    extracting: "提取中...",
    extractGlossaryFailed: "提取术语失败",
    cacheClearFailed: "清除缓存失败",
    addProvider: "添加自定义 Provider",
    providerName: "名称",
    providerNamePlaceholder: "例如：Local OpenAI",
    providerUrlPlaceholder: "https://example.com/v1",
    saveProvider: "保存 Provider",
    deleteProvider: "删除当前 Provider",
    selectedCustomProvider: "当前为自定义 Provider，只在本次页面会话中保留。",
    needFile: "请先选择 EPUB 文件。",
    needApiKey: "请填写 API Key。",
    needProviderName: "请填写 Provider 名称。",
    needProviderUrl: "请填写 Provider Base URL。",
    previewFailed: "解析失败",
    fetchModelsFailed: "获取模型失败",
    healthFailed: "连接测试失败",
    createJobFailed: "创建任务失败",
    providerSaved: "已添加自定义 Provider。",
    providerDeleted: "已删除自定义 Provider。",
    statusSummary: "已处理 {processed}/{total}，剩余 {pending}，当前进度 {progress}%。",
    languageNames: {
      Chinese: "中文",
      English: "英文",
      Japanese: "日文",
      Korean: "韩文",
      French: "法文",
      German: "德文",
      Spanish: "西班牙文"
    },
    statusNames: {
      idle: "未开始",
      running: "翻译中",
      paused: "已暂停",
      done: "已完成",
      empty: "无文本"
    }
  },
  en: {
    localPress: "local bilingual press",
    appTitle: "EPUB Bilingual Translator",
    heroCopy: "Turn a book into ordered passages, cache hits, translations, and a quiet reading copy.",
    language: "Language",
    manuscript: "Manuscript",
    manuscriptTitle: "Book & Workflow",
    chooseEpub: "Choose an EPUB",
    uploadHint: "Parse a preview after upload, then start translation.",
    parsePreview: "Parse Preview",
    startTranslation: "Start Translation",
    restartTranslation: "Restart Translation",
    progress: "Progress",
    progressTitle: "Translation Status",
    pause: "Pause",
    resume: "Resume",
    clear: "Clear",
    totalBlocks: "Total Blocks",
    processed: "Processed",
    cacheHits: "Cache Hits",
    failed: "Failures",
    pending: "Pending",
    status: "Status",
    download: "Download",
    bilingualEpub: "bilingual EPUB",
    failures: "Failed Blocks",
    retryFailures: "Retry Failed Blocks",
    preview: "Preview",
    previewTitle: "Parsed Preview",
    blockUnit: "text blocks",
    settings: "Settings",
    settingsTitle: "Translator Settings",
    provider: "Provider",
    apiKey: "API Key",
    baseUrl: "Base URL",
    model: "Model",
    fetchModels: "Fetch Models",
    testConnection: "Test Connection",
    targetLanguage: "Target Language",
    custom: "Custom",
    customTargetLanguage: "Custom Target Language",
    temperature: "Temperature",
    batchSize: "Batch Size",
    concurrency: "Concurrency",
    maxBlocks: "Max Blocks",
    stylePrompt: "Style Prompt",
    promptPlaceholder: "Example: warm, restrained prose with literary cadence.",
    glossary: "Glossary",
    glossaryPlaceholder: "Example:\nAlice=Alice\nKing's Landing=King's Landing",
    debug: "Debug & Connection Details",
    noConnection: "No connection test result yet",
    clearCache: "Clear Translation Cache",
    cacheCleared: "Cleared {count} cached rows.",
    extractGlossary: "Auto-Extract Terms",
    extracting: "Extracting...",
    extractGlossaryFailed: "Failed to extract terms",
    cacheClearFailed: "Failed to clear cache",
    addProvider: "Add Custom Provider",
    providerName: "Name",
    providerNamePlaceholder: "Example: Local OpenAI",
    providerUrlPlaceholder: "https://example.com/v1",
    saveProvider: "Save Provider",
    deleteProvider: "Delete Current Provider",
    selectedCustomProvider: "This custom Provider is kept only for the current page session.",
    needFile: "Choose an EPUB file first.",
    needApiKey: "Enter an API Key.",
    needProviderName: "Enter a Provider name.",
    needProviderUrl: "Enter a Provider Base URL.",
    previewFailed: "Preview failed",
    fetchModelsFailed: "Failed to fetch models",
    healthFailed: "Connection test failed",
    createJobFailed: "Failed to create job",
    providerSaved: "Custom Provider added.",
    providerDeleted: "Custom Provider deleted.",
    statusSummary: "Processed {processed}/{total}, {pending} pending, {progress}% complete.",
    languageNames: {
      Chinese: "Chinese",
      English: "English",
      Japanese: "Japanese",
      Korean: "Korean",
      French: "French",
      German: "German",
      Spanish: "Spanish"
    },
    statusNames: {
      idle: "Idle",
      running: "Running",
      paused: "Paused",
      done: "Done",
      empty: "Empty"
    }
  }
} as const;

function initialLanguage(): Language {
  const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
  return stored === "en" ? "en" : "zh";
}

async function jsonRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    }
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || `Request failed: ${response.status}`);
  }
  return data as T;
}

function slugify(value: string): string {
  return value.trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "custom-provider";
}

function uniqueProviderId(name: string, providers: Provider[]): string {
  const base = `custom-${slugify(name)}`;
  const ids = new Set(providers.map((provider) => provider.id));
  if (!ids.has(base)) return base;
  let index = 2;
  while (ids.has(`${base}-${index}`)) index += 1;
  return `${base}-${index}`;
}

function defaultTargetForLanguage(language: Language): string {
  return language === "en" ? "English" : "Chinese";
}

function numberOrDefault(value: string, fallback: number): number {
  if (value.trim() === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function App() {
  const [lang, setLang] = useState<Language>(initialLanguage);
  const copy = text[lang];
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<PreviewBlock[]>([]);
  const [previewTotal, setPreviewTotal] = useState(0);
  const [job, setJob] = useState<JobStatus>(emptyJob);
  const [apiKey, setApiKey] = useState("");
  const [providerId, setProviderId] = useState("openai");
  const [customProviders, setCustomProviders] = useState<Provider[]>([]);
  const [newProviderName, setNewProviderName] = useState("");
  const [newProviderUrl, setNewProviderUrl] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");
  const [models, setModels] = useState<string[]>([]);
  const [targetLanguage, setTargetLanguage] = useState(defaultTargetForLanguage(lang));
  const [targetLanguageTouched, setTargetLanguageTouched] = useState(false);
  const [customLanguage, setCustomLanguage] = useState("");
  const [temperature, setTemperature] = useState("0.7");
  const [batchSize, setBatchSize] = useState("4");
  const [concurrency, setConcurrency] = useState("4");
  const [maxBlocks, setMaxBlocks] = useState("0");
  const [customPrompt, setCustomPrompt] = useState("");
  const [glossary, setGlossary] = useState("");
  const [extractingGlossary, setExtractingGlossary] = useState(false);
  const [connection, setConnection] = useState<Record<string, unknown> | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  const providers = useMemo(() => {
    return [...(config?.providers || []), ...customProviders];
  }, [config, customProviders]);

  const selectedProvider = useMemo(() => {
    return providers.find((item) => item.id === providerId);
  }, [providerId, providers]);

  useEffect(() => {
    document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
    document.title = text[lang].appTitle;
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, lang);
  }, [lang]);

  useEffect(() => {
    refreshJob().catch(() => {});
    jsonRequest<AppConfig>("/api/config").then((data) => {
      setConfig(data);
      setProviderId(data.providers[0]?.id || "openai");
      setBaseUrl(data.providers[0]?.base_url || "");
      setModel(data.defaults.model);
      if (!targetLanguageTouched) {
        setTargetLanguage(defaultTargetForLanguage(lang));
      }
      setTemperature(String(data.defaults.temperature));
      setBatchSize(String(data.defaults.batch_size));
      setConcurrency(String(data.defaults.concurrency));
      setMaxBlocks(String(data.defaults.max_blocks));
    }).catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (selectedProvider) {
      setBaseUrl(selectedProvider.base_url);
      setModels([]);
    }
  }, [selectedProvider]);

  useEffect(() => {
    const active = ["running", "paused"].includes(job.status);
    const timer = window.setInterval(() => {
      if (active) {
        refreshJob();
      }
    }, 900);
    return () => window.clearInterval(timer);
  }, [job.status]);

  const finalTargetLanguage = useMemo(() => {
    return targetLanguage === "__custom__" ? (customLanguage.trim() || "Chinese") : targetLanguage;
  }, [targetLanguage, customLanguage]);

  const statusName = copy.statusNames[job.status as keyof typeof copy.statusNames] || job.status;
  const statusSummary = copy.statusSummary
    .replace("{processed}", String(job.processed_blocks))
    .replace("{total}", String(job.counts.total))
    .replace("{pending}", String(job.pending_blocks))
    .replace("{progress}", String(job.progress));

  async function refreshJob() {
    const data = await jsonRequest<JobStatus>("/api/jobs/current");
    setJob(data);
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    setFile(event.target.files?.[0] || null);
    setPreview([]);
    setPreviewTotal(0);
  }

  function changeLanguage(nextLanguage: Language) {
    if (!targetLanguageTouched || targetLanguage === defaultTargetForLanguage(lang)) {
      setTargetLanguage(defaultTargetForLanguage(nextLanguage));
    }
    setLang(nextLanguage);
    setMessage("");
  }

  function saveCustomProvider() {
    const name = newProviderName.trim();
    const url = newProviderUrl.trim();
    if (!name) {
      setMessage(copy.needProviderName);
      return;
    }
    if (!url) {
      setMessage(copy.needProviderUrl);
      return;
    }
    const provider: Provider = {
      id: uniqueProviderId(name, providers),
      name,
      base_url: url,
      custom: true
    };
    setCustomProviders((items) => [...items, provider]);
    setProviderId(provider.id);
    setBaseUrl(provider.base_url);
    setNewProviderName("");
    setNewProviderUrl("");
    setMessage(copy.providerSaved);
  }

  function deleteSelectedProvider() {
    if (!selectedProvider?.custom) return;
    setCustomProviders((items) => items.filter((item) => item.id !== selectedProvider.id));
    const fallback = config?.providers[0];
    setProviderId(fallback?.id || "openai");
    setBaseUrl(fallback?.base_url || "");
    setMessage(copy.providerDeleted);
  }

  async function parsePreview() {
    if (!file) {
      setMessage(copy.needFile);
      return;
    }
    setBusy(true);
    setMessage("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch("/api/preview", { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || copy.previewFailed);
      setPreview(data.preview);
      setPreviewTotal(data.total_blocks);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : copy.previewFailed);
    } finally {
      setBusy(false);
    }
  }

  async function fetchModels() {
    setBusy(true);
    setMessage("");
    try {
      const data = await jsonRequest<{ ok: boolean; models: string[]; error?: string }>("/api/models", {
        method: "POST",
        body: JSON.stringify({ base_url: baseUrl, api_key: apiKey })
      });
      if (!data.ok) throw new Error(data.error || copy.fetchModelsFailed);
      setModels(data.models);
      if (data.models[0]) setModel(data.models[0]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : copy.fetchModelsFailed);
    } finally {
      setBusy(false);
    }
  }

  async function testConnection() {
    setBusy(true);
    setMessage("");
    try {
      const data = await jsonRequest<Record<string, unknown>>("/api/health", {
        method: "POST",
        body: JSON.stringify({ base_url: baseUrl, api_key: apiKey, model, target_language: finalTargetLanguage })
      });
      setConnection(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : copy.healthFailed);
    } finally {
      setBusy(false);
    }
  }

  async function startJob(event: FormEvent) {
    event.preventDefault();
    if (!file) {
      setMessage(copy.needFile);
      return;
    }
    if (!apiKey) {
      setMessage(copy.needApiKey);
      return;
    }
    setBusy(true);
    setMessage("");
    const parsedTemperature = numberOrDefault(temperature, 0.7);
    const parsedBatchSize = Math.max(1, Math.floor(numberOrDefault(batchSize, 4)));
    const parsedConcurrency = Math.max(1, Math.floor(numberOrDefault(concurrency, 4)));
    const parsedMaxBlocks = Math.max(0, Math.floor(numberOrDefault(maxBlocks, 0)));
    const formData = new FormData();
    formData.append("file", file);
    formData.append("api_key", apiKey);
    formData.append("base_url", baseUrl);
    formData.append("model", model);
    formData.append("temperature", String(parsedTemperature));
    formData.append("batch_size", String(parsedBatchSize));
    formData.append("concurrency", String(parsedConcurrency));
    formData.append("custom_prompt", customPrompt);
    formData.append("glossary", glossary);
    formData.append("target_language", finalTargetLanguage);
    formData.append("max_blocks", String(parsedMaxBlocks));
    try {
      if (job.status === "paused") {
        await jsonRequest<JobStatus>("/api/jobs/current/stop", { method: "POST", body: "{}" });
      }
      const response = await fetch("/api/jobs", { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || copy.createJobFailed);
      setJob(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : copy.createJobFailed);
    } finally {
      setBusy(false);
    }
  }

  async function handleExtractGlossary() {
    if (!file) {
      setMessage(copy.needFile);
      return;
    }
    if (!apiKey) {
      setMessage(copy.needApiKey);
      return;
    }
    setExtractingGlossary(true);
    setMessage("");
    const formData = new FormData();
    formData.append("file", file);
    formData.append("api_key", apiKey);
    formData.append("base_url", baseUrl);
    formData.append("model", model);
    formData.append("target_language", finalTargetLanguage);
    try {
      const response = await fetch("/api/extract-glossary", { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || copy.extractGlossaryFailed);
      if (data.glossary) {
        setGlossary(prev => {
          const trimmed = prev.trim();
          return trimmed ? `${trimmed}\n${data.glossary}` : data.glossary;
        });
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : copy.extractGlossaryFailed);
    } finally {
      setExtractingGlossary(false);
    }
  }

  async function postJobAction(path: string) {
    setMessage("");
    try {
      const data = await jsonRequest<JobStatus>(path, { method: "POST", body: "{}" });
      setJob(data);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : copy.createJobFailed);
    }
  }

  async function clearTranslationCache() {
    setBusy(true);
    setMessage("");
    try {
      const data = await jsonRequest<{ ok: boolean; cleared: number }>("/api/cache/clear", {
        method: "POST",
        body: "{}"
      });
      setMessage(copy.cacheCleared.replace("{count}", String(data.cleared)));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : copy.cacheClearFailed);
    } finally {
      setBusy(false);
    }
  }

  function downloadOutput() {
    window.location.href = "/api/jobs/current/download";
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <p className="eyebrow">{copy.localPress}</p>
          <h1>{copy.appTitle}</h1>
          <p className="hero-copy">{copy.heroCopy}</p>
        </div>
        <div className="hero-side">
          <label className="language-switch">{copy.language}
            <select value={lang} onChange={(event) => changeLanguage(event.target.value as Language)}>
              <option value="zh">中文</option>
              <option value="en">English</option>
            </select>
          </label>
          <div className={`status status-${job.status}`}>
            <span>{statusName}</span>
            <strong>{job.progress}%</strong>
          </div>
        </div>
      </header>

      {message && <div className="notice">{message}</div>}

      <div className="layout">
        <section className="workspace">
          <form className="panel upload-panel" onSubmit={startJob}>
            <div className="panel-heading">
              <p className="section-kicker">{copy.manuscript}</p>
              <h2>{copy.manuscriptTitle}</h2>
            </div>
            <label className="dropzone">
              <input type="file" accept=".epub" onChange={onFileChange} />
              <span>{file ? file.name : copy.chooseEpub}</span>
              <small>{copy.uploadHint}</small>
            </label>
            <div className="actions">
              <button type="button" className="secondary" disabled={busy || !file} onClick={parsePreview}>{copy.parsePreview}</button>
              <button type="submit" disabled={busy || job.status === "running"}>
                {job.status === "paused" ? copy.restartTranslation : copy.startTranslation}
              </button>
            </div>
          </form>

          <section className="panel progress-panel">
            <div className="progress-top">
              <div>
                <p className="section-kicker">{copy.progress}</p>
                <h2>{copy.progressTitle}</h2>
                <p className="status-line">{statusSummary}</p>
              </div>
              <div className="job-actions">
                <button className="secondary" disabled={job.status !== "running"} onClick={() => postJobAction("/api/jobs/current/pause")}>{copy.pause}</button>
                <button className="secondary" disabled={job.status !== "paused"} onClick={() => postJobAction("/api/jobs/current/resume")}>{copy.resume}</button>
                <button className="ghost" disabled={job.status === "idle"} onClick={() => postJobAction("/api/jobs/current/stop")}>{copy.clear}</button>
              </div>
            </div>
            <div className="progress-track"><div style={{ width: `${job.progress}%` }} /></div>
            <div className="progress-details">
              <Metric label={copy.status} value={statusName} />
              <Metric label={copy.totalBlocks} value={job.counts.total} />
              <Metric label={copy.processed} value={job.processed_blocks} />
              <Metric label={copy.pending} value={job.pending_blocks} />
              <Metric label={copy.cacheHits} value={job.counts.cache_hits} />
              <Metric label={copy.failed} value={job.counts.failures} />
            </div>
            {job.can_download && (
              <button className="download" type="button" onClick={downloadOutput}>
                {copy.download} {job.output_name || copy.bilingualEpub}
              </button>
            )}
            {job.failures.length > 0 && (
              <div className="failures">
                <div className="row">
                  <strong>{copy.failures}</strong>
                  <button className="secondary" onClick={() => postJobAction("/api/jobs/current/retry-failures")}>{copy.retryFailures}</button>
                </div>
                {job.failures.map((failure) => (
                  <p key={failure.id}><b>{failure.id}</b> {failure.reason}</p>
                ))}
              </div>
            )}
          </section>

          {preview.length > 0 && (
            <section className="panel preview-panel">
              <div className="panel-heading">
                <p className="section-kicker">{copy.preview}</p>
                <h2>{copy.previewTitle} · {previewTotal} {copy.blockUnit}</h2>
              </div>
              <div className="preview-list">
                {preview.map((block) => (
                  <article key={block.block_id}>
                    <span>{block.tag}</span>
                    <p>{block.text}</p>
                  </article>
                ))}
              </div>
            </section>
          )}
        </section>

        <aside className="panel settings">
          <div className="panel-heading">
            <p className="section-kicker">{copy.settings}</p>
            <h2>{copy.settingsTitle}</h2>
          </div>
          <label>{copy.provider}
            <select value={providerId} onChange={(event) => setProviderId(event.target.value)}>
              {providers.map((provider) => <option key={provider.id} value={provider.id}>{provider.name}</option>)}
            </select>
          </label>
          {selectedProvider?.custom && (
            <div className="custom-provider-note">
              <span>{copy.selectedCustomProvider}</span>
              <button type="button" className="ghost compact" onClick={deleteSelectedProvider}>{copy.deleteProvider}</button>
            </div>
          )}
          <label>{copy.apiKey}
            <input type="password" value={apiKey} onChange={(event) => setApiKey(event.target.value)} />
          </label>
          <label>{copy.baseUrl}
            <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} />
          </label>
          <div className="inline">
            <label>{copy.model}
              {models.length > 0 ? (
                <select value={model} onChange={(event) => setModel(event.target.value)}>
                  {models.map((item) => <option key={item} value={item}>{item.replace(/^models\//, "")}</option>)}
                </select>
              ) : (
                <input value={model} onChange={(event) => setModel(event.target.value)} />
              )}
            </label>
            <button type="button" className="secondary fit" onClick={fetchModels}>{copy.fetchModels}</button>
          </div>
          <button type="button" className="secondary" onClick={testConnection}>{copy.testConnection}</button>
          <label>{copy.targetLanguage}
            <select value={targetLanguage} onChange={(event) => {
              setTargetLanguageTouched(true);
              setTargetLanguage(event.target.value);
            }}>
              {config?.target_languages.map((language) => (
                <option key={language} value={language}>
                  {copy.languageNames[language as keyof typeof copy.languageNames] || language}
                </option>
              ))}
              <option value="__custom__">{copy.custom}</option>
            </select>
          </label>
          {targetLanguage === "__custom__" && (
            <label>{copy.customTargetLanguage}
              <input value={customLanguage} placeholder="Traditional Chinese, Italian..." onChange={(event) => setCustomLanguage(event.target.value)} />
            </label>
          )}
          <div className="number-grid">
            <label>{copy.temperature}<input type="number" min="0" max="2" step="0.1" value={temperature} onChange={(event) => setTemperature(event.target.value)} /></label>
            <label>{copy.batchSize}<input type="number" min="1" value={batchSize} onChange={(event) => setBatchSize(event.target.value)} /></label>
            <label>{copy.concurrency}<input type="number" min="1" value={concurrency} onChange={(event) => setConcurrency(event.target.value)} /></label>
            <label>{copy.maxBlocks}<input type="number" min="0" value={maxBlocks} onChange={(event) => setMaxBlocks(event.target.value)} /></label>
          </div>
          <label>{copy.stylePrompt}
            <textarea rows={3} value={customPrompt} onChange={(event) => setCustomPrompt(event.target.value)} placeholder={copy.promptPlaceholder} />
          </label>
          <label>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                <span>{copy.glossary}</span>
                <button type="button" className="secondary compact" disabled={extractingGlossary} onClick={handleExtractGlossary} style={{ padding: '2px 8px', fontSize: '0.8em', margin: 0 }}>
                    {extractingGlossary ? copy.extracting : copy.extractGlossary}
                </button>
            </div>
            <textarea rows={4} value={glossary} onChange={(event) => setGlossary(event.target.value)} placeholder={copy.glossaryPlaceholder} />
          </label>
          <details className="custom-provider">
            <summary>{copy.addProvider}</summary>
            <div className="provider-form">
              <label>{copy.providerName}
                <input value={newProviderName} placeholder={copy.providerNamePlaceholder} onChange={(event) => setNewProviderName(event.target.value)} />
              </label>
              <label>{copy.baseUrl}
                <input value={newProviderUrl} placeholder={copy.providerUrlPlaceholder} onChange={(event) => setNewProviderUrl(event.target.value)} />
              </label>
              <button type="button" className="secondary" onClick={saveCustomProvider}>{copy.saveProvider}</button>
            </div>
          </details>
          <details className="debug">
            <summary>{copy.debug}</summary>
            <button type="button" className="secondary clear-cache" disabled={busy} onClick={clearTranslationCache}>
              {copy.clearCache}
            </button>
            <pre>{connection ? JSON.stringify(connection, null, 2) : copy.noConnection}</pre>
          </details>
        </aside>
      </div>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

export default App;
