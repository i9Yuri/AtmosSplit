"""Trabalhos de estúdio isolados. O protocolo transmite metadados e poses; o áudio fica local."""

from __future__ import annotations

import json
import math
import sys
from dataclasses import asdict, fields
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..spatial.timeline_manager import SpatialSection


def pack_sections(sections: list[SpatialSection]) -> list[dict]:
    return [
        {**{f.name: getattr(section, f.name) for f in fields(section)
            if f.name not in ("placements", "micro_events")},
         "placements": {name: asdict(p) for name, p in section.placements.items() if not name.endswith("::micro")},
         "micro_events": [asdict(event) for event in section.micro_events]}
        for section in sections
    ]


def unpack_sections(data: list[dict]) -> list[SpatialSection]:
    from ..spatial.auto_director import SpatialPlacement
    from ..spatial.micro_events import SpatialEvent
    from ..spatial.timeline_manager import SpatialSection
    sections = []
    for row in data:
        values = row.copy()
        values["placements"] = {name: SpatialPlacement(**p) for name, p in row["placements"].items()
                                if not name.endswith("::micro")}
        values["micro_events"] = tuple(SpatialEvent(**event) for event in row.get("micro_events", ()))
        values.setdefault("micro_enabled", True)
        if "downbeats_s" in values:
            values["downbeats_s"] = tuple(values["downbeats_s"])
        sections.append(SpatialSection(**values))
    return sections


def read_arrangement(path: Path, duration: float, names: set[str]) -> dict:
    from ..spatial.auto_director import DirectorPreset
    saved = json.loads(path.read_text(encoding="utf8"))
    sections = unpack_sections(saved["sections"])
    if saved["version"] != 1 or not sections or abs(sections[-1].end_time_s-duration) > 0.015:
        raise ValueError("duração incompatível")
    if sections[0].start_time_s != 0 or len({s.id for s in sections}) != len(sections):
        raise ValueError("seções inválidas")
    for i, section in enumerate(sections):
        if not 0 <= section.start_time_s < section.end_time_s <= duration + 0.015:
            raise ValueError("limites inválidos")
        if i and sections[i-1].end_time_s != section.start_time_s:
            raise ValueError("trechos descontínuos")
        if not section.placements or any(not math.isfinite(t) for t in section.downbeats_s):
            raise ValueError("automação inválida")
        if not isinstance(section.micro_enabled, bool) or any(
            not isinstance(ev.kind, str) or ev.stem not in names or not (0 <= ev.start_s < ev.end_s <= duration + .015)
            for ev in section.micro_events
        ):
            raise ValueError("microcoreografia inválida")
        for name, p in section.placements.items():
            if (p.source_stem_name or name) not in names or p.stem_name != name:
                raise ValueError("fontes diferentes do cache atual")
            if not (-1 <= p.x <= 1 and -1 <= p.y <= 1 and 0 <= p.z <= 1 and
                    0 <= p.spread <= 1 and 0 <= p.lfe_send <= 1 and math.isfinite(p.volume_gain) and p.volume_gain >= 0):
                raise ValueError("posição ou ganho inválido")
    return {"sections": pack_sections(sections), "preset": DirectorPreset(saved["preset"]).value,
            "intensity": max(0, min(100, int(saved["intensity"]))), "manual": bool(saved.get("manual")),
            "missing_micro": [row["id"] for row in saved["sections"] if "micro_events" not in row]}


def _emit(kind: str, **fields) -> None:
    print(json.dumps({"type": kind, **fields}, ensure_ascii=False), flush=True)


def _progress(text: str, value: float = -1) -> None:
    _emit("progress", text=text, value=value)


def execute(request: dict) -> dict:
    action = request["action"]
    if action in ("search", "download"):
        from ..acquisition.search_source import SearchResultItem, SearchSourceEngine
        search = SearchSourceEngine()
        if action == "search":
            return {"results": [asdict(r) for r in search.search(request["query"])]}
        return {"path": str(search.download_to_file(SearchResultItem(**request["item"])))}

    from ..separation.cache_manager import StemCacheManager
    from ..separation.stem_engine import DeepStemEngine
    from ..spatial.auto_director import DirectorPreset
    from ..spatial.song_intelligence import SongStructureIntelligence
    from ..spatial.timeline_manager import SpatialTimelineManager
    engine = DeepStemEngine(StemCacheManager(Path(request["cache"])))
    mode = request["mode"]
    if action == "prepare":
        from ..acquisition.file_source import load_audio_file, populate_audio
        _progress("Identificando metadados e calculando assinatura de áudio…", 0.05)
        source = load_audio_file(request["path"], load_data_now=False)
        details = {"hash": source.sha256_hash, "path": str(source.file_path), "title": source.metadata.title,
                   "artist": source.metadata.artist, "format": source.metadata.format_name, "sr": source.sample_rate}
        warning = ""
        if request["restore"]:
            manifest = engine.cache_manager.get_manifest(source.sha256_hash, mode)
            if manifest:
                path = Path(request["session_dir"]) / f"{source.sha256_hash}_{mode}.json"
                try:
                    saved = read_arrangement(path, max(m.duration_s for m in manifest), {m.stem_name for m in manifest})
                except FileNotFoundError:
                    pass
                except (OSError, ValueError, AttributeError, KeyError, TypeError) as exc:
                    warning = f"Automação salva incompatível. Nova análise carregada ({exc})."
                else:
                    missing = set(saved.pop("missing_micro"))
                    if missing:
                        from ..spatial.micro_events import detect_micro_events
                        _progress("Detectando microeventos espaciais na sessão salva…", 0.96)
                        cached = engine.load_cached_result(source.sha256_hash, mode)
                        if not cached:
                            raise RuntimeError("Os stems da sessão salva ficaram indisponíveis.")
                        sections = unpack_sections(saved["sections"])
                        # O detector usa a posição absoluta e o contexto da faixa inteira.
                        preserved = {s.id: s.micro_events for s in sections if s.id not in missing}
                        detect_micro_events(cached.stems, sections, intensity=saved["intensity"]/100)
                        for section in sections:
                            if section.id in preserved:
                                section.micro_events = preserved[section.id]
                        saved.update(sections=pack_sections(sections), micro_migrated=True)
                    return {**details, **saved, "restored": True}
        _progress("Carregando e decodificando áudio…", 0.10)
        source = populate_audio(source)

        def separation_progress(value: float, message: str) -> None:
            # A conclusão do motor ainda deixa a análise e a montagem do monitor pendentes.
            if 0.15 <= value <= 0.70:
                value = 0.15 + (value - 0.15) * (0.60 / 0.55)
            if value < 1.0:
                _progress(message, value)

        result = engine.separate_track(
            source.audio_data, source.sample_rate, source.sha256_hash, mode,
            progress_callback=separation_progress,
        )
        duration = max(len(s.audio_data) / s.sample_rate for s in result.stems)
        _progress("Analisando estrutura musical, BPM, seções e microeventos…", 0.90)
        sections = SongStructureIntelligence.analyze_and_arrange(
            result.stems, duration, DirectorPreset(request["preset"]), intensity=request["intensity"],
            mix_audio=source.audio_data, mix_sample_rate=source.sample_rate,
        )
        _progress("Compilando a automação espacial…", 0.96)
        for section in sections:
            section.micro_enabled = request.get("micro_enabled", True)
        return {**details, "sections": pack_sections(sections), "preset": request["preset"],
                "intensity": round(100 * request["intensity"]), "restored": False, "warning": warning}

    result = engine.load_cached_result(request["hash"], mode)
    if not result:
        raise RuntimeError("Os stems saíram do cache. Abra a faixa para prepará-los novamente.")
    sections = unpack_sections(request["sections"])
    if action == "redirect":
        enabled = {s.id: s.micro_enabled for s in sections}
        arranged = SongStructureIntelligence.redirect(sections, result.stems, DirectorPreset(request["preset"]),
                                                     request["intensity"])
        for section in arranged:
            section.micro_enabled = enabled[section.id]
        return {"sections": pack_sections(arranged)}

    if action != "export":
        raise ValueError(f"Trabalho desconhecido: {action}")
    from ..acquisition.file_source import extract_metadata_from_file
    from ..playback.exporter import AudioExporter714, ExportFormat
    from ..spatial.master_renderer import MasterRenderer714, RenderConfig
    timeline = SpatialTimelineManager(sections[-1].end_time_s)
    timeline.set_sections(sections)
    renderer = MasterRenderer714()
    _progress("Renderizando automação e medindo o master 7.1.4…")
    matrix = renderer.render_to_multichannel_714(
        result.stems, sections[0].placements, config=RenderConfig(sample_rate=48000, profile=request["profile"]),
        timeline_manager=timeline,
    )
    _progress("Codificando o arquivo de entrega…")
    delivery = AudioExporter714.export_verified(matrix, Path(request["staging"]), 48000, ExportFormat(request["format"]),
                                                metadata=extract_metadata_from_file(Path(request["path"])))
    report = renderer.last_report
    meters = {}
    for key in ("integrated_lufs", "true_peak_dbtp", "vocal_balance_db", "presence_balance_db"):
        val = getattr(report, key)
        meters[key] = float(val) if val is not None and math.isfinite(val) else None
    if delivery.joc is not None:
        meters.update(asdict(delivery.joc))
    return {"report": meters}


def main() -> int:
    try:
        from ..separation.process_shield import apply_process_shield
        apply_process_shield(reserve_cores=2)
        _emit("done", result=execute(json.load(sys.stdin)))
        return 0
    except Exception as error:
        import traceback
        traceback.print_exc(file=sys.stderr)
        _emit("error", text=str(error))
        return 1


if __name__ == "__main__":
    sys.exit(main())
