import datetime
import json
import logging
from typing import Any, Dict

import azure.functions as func

from extractor.runner import ExtractionRunner


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


def _extract_job_name(payload: Dict[str, Any]) -> str:
    job_name = payload.get("job_name")
    if not job_name:
        raise ValueError("Missing required field: job_name")
    return str(job_name)


@app.route(route="extract", methods=["POST"])
def extract_http(req: func.HttpRequest) -> func.HttpResponse:
    start = datetime.datetime.utcnow()
    logging.info("Generic extractor HTTP trigger started at %s", start.isoformat())

    try:
        payload = req.get_json()
        job_name = _extract_job_name(payload)

        runner = ExtractionRunner.from_azure_environment()
        result = runner.run_from_adls(job_name)

        end = datetime.datetime.utcnow()
        body = {
            "status": "ok",
            "job_name": job_name,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
            "records_extracted": result["records_extracted"],
            "output_path": result["output_path"],
        }
        return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")
    except Exception as exc:
        logging.exception("Extraction failed: %s", exc)
        return func.HttpResponse(
            json.dumps({"status": "error", "message": str(exc)}),
            status_code=500,
            mimetype="application/json",
        )


@app.timer_trigger(schedule="%DEFAULT_TIMER_SCHEDULE%", arg_name="timer", run_on_startup=False, use_monitor=True)
def extract_timer(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("Timer trigger is running late")

    logging.info("Timer trigger fired at %s", datetime.datetime.utcnow().isoformat())

    default_job_name = ""
    try:
        import os

        default_job_name = os.getenv("DEFAULT_JOB_NAME", "")
        if not default_job_name:
            logging.info("DEFAULT_JOB_NAME is not configured; skipping timer execution")
            return

        runner = ExtractionRunner.from_azure_environment()
        result = runner.run_from_adls(default_job_name)

        logging.info(
            "Timer extraction complete for job %s. records=%s output_path=%s",
            default_job_name,
            result["records_extracted"],
            result["output_path"],
        )
    except Exception as exc:
        logging.exception("Timer extraction failed for job %s: %s", default_job_name, exc)
        raise
