import traceback
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Query
from models import UploadResponse
from services.file_parser import parse_file, ALLOWED_EXTENSIONS

router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_config(file: UploadFile = File(...), request: Request = None):
    filename = file.filename or "upload"
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()

    try:
        text, sheets = parse_file(content, ext)
    except Exception as e:
        print(f"[Upload] Parse error for '{filename}':\n{traceback.format_exc()}")
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

    try:
        request.app.state.uploaded_impact_config_dfs[filename] = sheets
        chunks_added = request.app.state.rag.add_uploaded_document(text, filename)
    except Exception as e:
        print(f"[Upload] Storage error for '{filename}':\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to index document: {e}")

    sheet_stats = [{"label": name, "value": len(df)} for name, df in sheets.items()]

    return UploadResponse(
        message=f"✅ **'{filename}'** uploaded successfully.",
        chunks_added=chunks_added,
        filename=filename,
        sheet_stats=sheet_stats,
    )


@router.delete("/upload")
async def clear_upload_state(request: Request, purpose: str = Query("impact")):
    if purpose == "release":
        request.app.state.uploaded_release_dfs.clear()
    else:
        request.app.state.uploaded_impact_config_dfs.clear()
    return {"cleared": True, "purpose": purpose}
