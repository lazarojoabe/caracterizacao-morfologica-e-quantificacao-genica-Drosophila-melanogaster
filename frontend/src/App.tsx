import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Download, FolderOpen, LoaderCircle, Redo2, RefreshCw, Undo2 } from "lucide-react";
import { createSession, edit, exportUrl, getResult, reprocess, subscribeJob, undo, redo } from "./api";
import { ImageViewer } from "./components/ImageViewer";
import { MetricsPanel } from "./components/MetricsPanel";
import { NucleiTable } from "./components/NucleiTable";
import type { Config, Job, Result, SelectionModifiers } from "./types";

const defaults: Config = {
  nucleus_channel: 0,
  protein_channel: 2,
  gaussian_kernel: 5,
  gaussian_sigma: 1,
  opening_kernel: 3,
  closing_kernel: 5,
  min_nucleus_area: 100,
  pixel_size: null,
  pixel_unit: "µm",
  input_mode: "auto",
};

interface ScrollSnapshot {
  windowX: number;
  windowY: number;
  elements: Array<{ element: HTMLElement; left: number; top: number }>;
}

function uniqueIds(ids: number[]) {
  return [...new Set(ids)];
}

export default function App() {
  const [nucleusFile, setNucleusFile] = useState<File>();
  const [proteinFile, setProteinFile] = useState<File>();
  const [config, setConfig] = useState<Config>(defaults);
  const [result, setResult] = useState<Result>();
  const [job, setJob] = useState<Job>();
  const [selected, setSelected] = useState<number[]>([]);
  const [selectionAnchor, setSelectionAnchor] = useState<number | null>(null);
  const [layer, setLayer] = useState<"nucleus" | "protein" | "mask">("protein");
  const [labels, setLabels] = useState(true);
  const [editId, setEditId] = useState<number | null>(null);
  const [editPolygon, setEditPolygon] = useState<[number, number][] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const pendingScroll = useRef<ScrollSnapshot | null>(null);

  const selectedNucleus = result?.nuclei.find((nucleus) => nucleus.nucleus_id === selected[0]);
  const visibleNuclei = useMemo(
    () => (result?.nuclei ?? []).filter((nucleus) => !filter || String(nucleus.nucleus_id).includes(filter)),
    [result, filter],
  );
  const busy = job?.status === "queued" || job?.status === "running";

  useLayoutEffect(() => {
    const snapshot = pendingScroll.current;
    if (!snapshot) return;

    window.scrollTo(snapshot.windowX, snapshot.windowY);
    snapshot.elements.forEach(({ element, left, top }) => {
      if (element.isConnected) {
        element.scrollLeft = left;
        element.scrollTop = top;
      }
    });
    pendingScroll.current = null;
  }, [result?.revision]);

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if (!(event.ctrlKey || event.metaKey)) return;
      if (event.key.toLowerCase() === "z") {
        event.preventDefault();
        void historyAction(undo);
      } else if (event.key.toLowerCase() === "y") {
        event.preventDefault();
        void historyAction(redo);
      }
    }

    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [result]);

  function captureScroll(): ScrollSnapshot {
    return {
      windowX: window.scrollX,
      windowY: window.scrollY,
      elements: Array.from(document.querySelectorAll<HTMLElement>(".panel, .table-panel, .workspace")).map((element) => ({
        element,
        left: element.scrollLeft,
        top: element.scrollTop,
      })),
    };
  }

  function commitResult(next: Result) {
    pendingScroll.current = captureScroll();
    setResult(next);
  }

  async function refresh(id = result?.session_id) {
    if (!id) return;
    try {
      const next = await getResult(id);
      commitResult(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Falha ao atualizar");
    }
  }

  function selectNucleus(id: number, modifiers: SelectionModifiers) {
    const orderedIds = visibleNuclei.map((nucleus) => nucleus.nucleus_id);
    const anchorIndex = selectionAnchor === null ? -1 : orderedIds.indexOf(selectionAnchor);
    const currentIndex = orderedIds.indexOf(id);

    if (modifiers.range && anchorIndex >= 0 && currentIndex >= 0) {
      const start = Math.min(anchorIndex, currentIndex);
      const end = Math.max(anchorIndex, currentIndex);
      const range = orderedIds.slice(start, end + 1);
      setSelected((current) => modifiers.additive ? uniqueIds([...current, ...range]) : range);
    } else if (modifiers.additive) {
      setSelected((current) => current.includes(id)
        ? current.filter((value) => value !== id)
        : [...current, id]);
    } else {
      setSelected([id]);
    }
    setSelectionAnchor(id);
  }

  function selectAll(ids: number[]) {
    if (!ids.length) return;
    const selectedAll = ids.every((id) => selected.includes(id));
    const idSet = new Set(ids);
    setSelected((current) => selectedAll
      ? current.filter((id) => !idSet.has(id))
      : uniqueIds([...current, ...ids]));
    setSelectionAnchor(ids[ids.length - 1]);
  }

  async function openImages() {
    if (!nucleusFile || !proteinFile) {
      setError("Selecione uma imagem de núcleos e uma de proteína.");
      return;
    }
    try {
      setError("");
      setSelected([]);
      setSelectionAnchor(null);
      const session = await createSession(nucleusFile, proteinFile, config);
      setJob({
        job_id: session.job_id,
        session_id: session.session_id,
        status: session.status,
        progress: 0,
        message: "Aguardando processamento",
        error: null,
      });
      subscribeJob(
        session.session_id,
        (next) => setJob(next),
        () => void refresh(session.session_id),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Falha ao abrir as imagens");
    }
  }

  async function apply(operation: "hide" | "exclude" | "restore") {
    if (!result || !selected.length) return;
    try {
      const next = await edit(result.session_id, {
        operation,
        nucleus_ids: selected,
        base_revision: result.revision,
      });
      commitResult(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Falha na edição");
      await refresh();
    }
  }

  async function historyAction(action: typeof undo) {
    if (!result) return;
    try {
      const next = await action(result.session_id, result.revision);
      commitResult(next);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Falha no histórico");
    }
  }

  async function startReprocess() {
    if (!result || !window.confirm("Reprocessar descarta os identificadores e as edições atuais. Continuar?")) return;
    try {
      const next = await reprocess(result.session_id, result.revision, config);
      setJob(next);
      subscribeJob(result.session_id, (nextJob) => setJob(nextJob), () => void refresh());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Falha ao reprocessar");
    }
  }

  async function saveContour() {
    if (!result || !editId || !editPolygon) return;
    try {
      const next = await edit(result.session_id, {
        operation: "edit_contour",
        nucleus_id: editId,
        nucleus_ids: [editId],
        polygon: editPolygon,
        base_revision: result.revision,
      });
      commitResult(next);
      setEditId(null);
      setEditPolygon(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Contorno inválido");
    }
  }

  return <div className="app-shell">
    <header className="topbar">
      <div className="brand"><div className="brand-mark">NR</div><div><strong>Nuclei Review</strong><small>Revisão quantitativa de imagens</small></div></div>
      <div className="toolbar">
        <button className="primary" onClick={() => document.getElementById("nuclei-input")?.click()}><FolderOpen size={16} /> Abrir imagens</button>
        <button onClick={() => result && window.open(exportUrl(result.session_id, "json"), "_blank")} disabled={!result}><Download size={16} /> Exportar JSON</button>
        <button onClick={() => result && window.open(exportUrl(result.session_id, "csv"), "_blank")} disabled={!result}>CSV</button>
        <button onClick={() => void historyAction(undo)} disabled={!result}><Undo2 size={16} /></button>
        <button onClick={() => void historyAction(redo)} disabled={!result}><Redo2 size={16} /></button>
        <button onClick={() => void startReprocess()} disabled={!result || busy}><RefreshCw size={16} /> Reprocessar</button>
        {busy && <span className="job-status"><LoaderCircle size={15} className="spin" /> {job?.progress}%</span>}
      </div>
    </header>

    <input id="nuclei-input" type="file" accept=".tif,.tiff,.png,.jpg,.jpeg" hidden onChange={(event) => setNucleusFile(event.target.files?.[0])} />

    <main className="workspace">
      <aside className="panel left">
        <div className="panel-heading"><span>Entrada</span><span className="eyebrow">ASSISTENTE</span></div>
        <label>Imagem de núcleos<input type="file" accept=".tif,.tiff,.png,.jpg,.jpeg" onChange={(event) => setNucleusFile(event.target.files?.[0])} /></label>
        {nucleusFile && <div className="file-chip">{nucleusFile.name}</div>}
        <label>Imagem de proteína<input type="file" accept=".tif,.tiff,.png,.jpg,.jpeg" onChange={(event) => setProteinFile(event.target.files?.[0])} /></label>
        {proteinFile && <div className="file-chip">{proteinFile.name}</div>}
        <button className="primary full" onClick={() => void openImages()} disabled={busy}>{busy ? "Processando…" : "Processar par"}</button>

        <div className="rule" />
        <div className="panel-heading"><span>Canais e escala</span></div>
        <div className="two-col">
          <label>Canal núcleos<input type="number" min="0" value={config.nucleus_channel} onChange={(event) => setConfig({ ...config, nucleus_channel: Number(event.target.value) })} /></label>
          <label>Canal proteína<input type="number" min="0" value={config.protein_channel} onChange={(event) => setConfig({ ...config, protein_channel: Number(event.target.value) })} /></label>
        </div>
        <div className="two-col">
          <label>Pixel<input type="number" min="0" step="0.001" placeholder="opcional" value={config.pixel_size ?? ""} onChange={(event) => setConfig({ ...config, pixel_size: event.target.value ? Number(event.target.value) : null })} /></label>
          <label>Unidade<input value={config.pixel_unit} onChange={(event) => setConfig({ ...config, pixel_unit: event.target.value })} /></label>
        </div>
        <label>Tipo de entrada<select value={config.input_mode} onChange={(event) => setConfig({ ...config, input_mode: event.target.value as Config["input_mode"] })}><option value="auto">Detectar automaticamente</option><option value="raw">TIFF/PNG bruto</option><option value="derived">Resultado derivado (avisar)</option></select></label>

        <div className="rule" />
        <div className="panel-heading"><span>Segmentação</span></div>
        <label>Área mínima<input type="number" min="1" value={config.min_nucleus_area} onChange={(event) => setConfig({ ...config, min_nucleus_area: Number(event.target.value) })} /></label>
        {result && <div className="info-card"><strong>{result.aggregate.nucleus_count ?? 0} núcleos ativos</strong><span>revisão {result.revision} · {result.shape?.width}×{result.shape?.height}px</span></div>}
      </aside>

      <section className="center">
        <div className="canvas-header">
          <div><span className="eyebrow">AMOSTRA</span><strong>{result ? result.session_id.slice(0, 12) : "Nenhuma sessão aberta"}</strong></div>
          <div className="layer-tabs">
            {(["nucleus", "protein", "mask"] as const).map((item) => <button key={item} className={layer === item ? "active" : ""} onClick={() => setLayer(item)} disabled={!result}>{item === "nucleus" ? "Núcleos" : item === "protein" ? "Proteína" : "Máscara"}</button>)}
            <label className="check"><input type="checkbox" checked={labels} onChange={(event) => setLabels(event.target.checked)} /> IDs</label>
          </div>
        </div>

        <ImageViewer
          sessionId={result?.session_id ?? null}
          shape={result?.shape ?? null}
          nuclei={result?.nuclei ?? []}
          selected={selected}
          layer={layer}
          labels={labels}
          editId={editId}
          onSelect={selectNucleus}
          onEditChange={setEditPolygon}
        />

        <div className="table-panel">
          <div className="table-header">
            <div className="table-heading"><strong>Todos os núcleos</strong><span className="selection-count" aria-live="polite">{selected.length ? `${selected.length} selecionado(s)` : "Nenhum selecionado"}</span></div>
            <input placeholder="Pesquisar ID" value={filter} onChange={(event) => setFilter(event.target.value)} />
          </div>
          <div className="selection-bar">
            <span>Ctrl/Cmd + clique adiciona · Shift + clique seleciona um intervalo</span>
            <div className="bulk-actions">
              <button className="danger" disabled={!selected.length} onClick={() => void apply("exclude")}>Excluir selecionados</button>
              <button disabled={!selected.length} onClick={() => void apply("restore")}>Restaurar selecionados</button>
              <button disabled={!selected.length} onClick={() => { setSelected([]); setSelectionAnchor(null); }}>Limpar</button>
            </div>
          </div>
          <NucleiTable nuclei={visibleNuclei} selected={selected} onSelect={selectNucleus} onSelectAll={selectAll} />
        </div>
      </section>

      <MetricsPanel
        nucleus={selectedNucleus}
        revision={result?.revision ?? 0}
        onAction={(operation) => void apply(operation)}
        editing={editId !== null}
        onEdit={() => selectedNucleus && setEditId(selectedNucleus.nucleus_id)}
        onSave={() => void saveContour()}
        onCancel={() => { setEditId(null); setEditPolygon(null); }}
      />
    </main>

    {result?.warnings.map((warning) => <div className="toast warning" key={warning}>Aviso: {warning}</div>)}
    {error && <div className="toast error" onClick={() => setError("")}>{error}</div>}
  </div>;
}
