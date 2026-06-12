import traceback
from fastapi import APIRouter, UploadFile, File, HTTPException, Request
from models import UploadResponse
from services.file_parser import parse_file, ALLOWED_EXTENSIONS

router = APIRouter()


@router.post("/upload-release", response_model=UploadResponse)
async def upload_release(file: UploadFile = File(...), request: Request = None):
    filename = file.filename or "release"
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
        print(f"[Release Upload] Parse error:\n{traceback.format_exc()}")
        raise HTTPException(status_code=422, detail=f"Could not parse file: {e}")

    request.app.state.uploaded_release_dfs[filename] = sheets

    sheet_stats = [{"label": name, "value": len(df)} for name, df in sheets.items()]

    return UploadResponse(
        message=f"✅ **'{filename}'** uploaded — {len(sheets)} section(s) ready for analysis.",
        chunks_added=len(sheets),
        filename=filename,
        sheet_stats=sheet_stats,
    )
