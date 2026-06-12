import traceback
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from models import UploadResponse
from services.file_parser import parse_file, ALLOWED_EXTENSIONS
from services.integration_analysis_service import analyze_integration_spec

router = APIRouter()


@router.post("/upload-integration", response_model=UploadResponse)
async def upload_integration_spec(file: UploadFile = File(...), request: Request = None):
    filename = file.filename or "integration_spec"
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    try:
        _, sheets = parse_file(content, ext)
    except Exception as e:
        print(f"[Integration Upload] Parse error:\n{traceback.format_exc()}")
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

    request.app.state.uploaded_integration_spec_dfs[filename] = sheets

    sheet_stats = [{"label": name, "value": len(df)} for name, df in sheets.items()]
    return UploadResponse(
        message=f"✅ **'{filename}'** uploaded — {len(sheets)} section(s) ready for Stage 2 analysis.",
        chunks_added=len(sheets),
        filename=filename,
        sheet_stats=sheet_stats,
    )


@router.post("/analyze-integration")
async def analyze_integration(request: Request):
    impact_report = getattr(request.app.state, "cached_impact_report", "")
    spec_dfs      = getattr(request.app.state, "uploaded_integration_spec_dfs", {})

    if not impact_report:
        raise HTTPException(
            status_code=400,
            detail="Stage 1 analysis must be run first. Upload Release Doc + Config Report and run the impact analysis."
        )
    if not spec_dfs:
        raise HTTPException(
            status_code=400,
            detail="No Integration Specification uploaded. Please upload your integration spec file."
        )

    latest_key = list(spec_dfs.keys())[-1]
    raw_report = analyze_integration_spec(impact_report, spec_dfs[latest_key])

    bedrock = getattr(request.app.state, "bedrock", None)
    if bedrock and bedrock.is_configured():
        raw_report = bedrock.enhance_integration_report(raw_report, impact_report)

    request.app.state.cached_integration_report = raw_report
    return {"report": raw_report}


@router.delete("/upload-integration")
async def clear_integration(request: Request):
    request.app.state.uploaded_integration_spec_dfs.clear()
    request.app.state.cached_integration_report = ""
    return {"cleared": True}
