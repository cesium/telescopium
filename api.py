from concurrent.futures import ThreadPoolExecutor
from pydantic import BaseModel, ValidationError

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.requests import Request
from starlette.routing import Route

from scraper import Scraper

import datetime
import uvicorn
import json
import uuid

DEFAULT_COURSE_NAME = "Licenciatura em Engenharia Informática"


class Week(BaseModel):
    start: str | None = None
    end: str | None = None


class ScheduleRequest(BaseModel):
    timeout: int = 1
    course: str = DEFAULT_COURSE_NAME
    years: list[int] | None = None
    week: Week | None = None
    classes: list[str] | None = None

    def to_scraper_config(self) -> dict:
        today = datetime.date.today()
        week = self.week or Week()
        start = week.start or today.isoformat()
        end = week.end or (today + datetime.timedelta(days=14)).isoformat()
        years = self.years or [1, 2, 3]

        config = {
            "timeout": self.timeout,
            "course_name": self.course,
            "year": years,
            "week": {
                "start": start,
                "end": end,
            },
        }

        if self.classes is not None:
            config["classes"] = self.classes

        return config


class Job:
    def __init__(self, id: uuid.UUID):
        self.id = id
        self.status = "created"
        self.result = None
        self.created_at = datetime.datetime.now()
        self.completed_at = None

    def to_dict(self):
        return {
            "id": str(self.id),
            "status": self.status,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "completed_at": (
                self.completed_at.strftime("%Y-%m-%d %H:%M:%S")
                if self.completed_at
                else None
            ),
        }

    def run(self, config: dict | None = None):
        if config is None:
            config = ScheduleRequest().to_scraper_config()

        self.status = "running"
        try:
            scraper = Scraper(config)

            unique_shifts = {}
            for shift in scraper.shifts:
                unique_shifts.setdefault(shift.id, shift)

            self.result = [shift.to_dict() for shift in unique_shifts.values()]
            self.completed_at = datetime.datetime.now().replace(microsecond=0)
            self.status = "done"
        except Exception as e:
            self.status = "failed"
            print(f"Job {self.id} failed: {e}")


class API:
    def __init__(self):
        self.__jobs: dict[uuid.UUID, Job] = {}
        self.__executor = ThreadPoolExecutor(max_workers=1)

        self.__starlette = Starlette(
            routes=[
                Route("/api/v1/scrape", self.__run_scraper, methods=["POST"]),
                Route("/api/v1/shifts", self.__get_shifts, methods=["GET"]),
                Route(
                    "/api/v1/shifts/{job_id:uuid}", self.__get_shifts, methods=["GET"]
                ),
                Route("/api/v1/jobs", self.__list_jobs, methods=["GET"]),
                Route("/api/v1/jobs/{job_id:uuid}", self.__list_jobs, methods=["GET"]),
            ]
        )

    def run(self, host: str, port: int) -> None:
        uvicorn.run(self.__starlette, host=host, port=port)

    async def __run_scraper(self, request):
        try:
            body = await request.body()
            payload = json.loads(body) if body else {}
            if "course_name" in payload and "course" not in payload:
                payload["course"] = payload["course_name"]
            if "year" in payload and "years" not in payload:
                payload["years"] = payload["year"]
            data = ScheduleRequest.model_validate(payload)
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse({"error": str(e)}, status_code=422)

        try:
            job_id = uuid.uuid4()
            job = Job(job_id)
            self.__jobs[job_id] = job
            self.__executor.submit(job.run, data.to_scraper_config())

            return JSONResponse({"job_id": str(job_id)})

        except Exception as e:
            return JSONResponse(
                {"error": f"Something went wrong! Error: {e}"},
                status_code=500,
            )

    async def __list_jobs(self, request):
        job_id = request.path_params.get("job_id")

        if job_id:
            job = self.__jobs.get(job_id)
            if job is None:
                return JSONResponse({"error": "Job not found"}, status_code=404)
            return JSONResponse(job.to_dict())
        else:
            return JSONResponse(
                {"jobs": [job.to_dict() for job in self.__jobs.values()]}
            )

    async def __get_shifts(self, request: Request):
        job_id = request.path_params.get("job_id")
        job = (
            self.__jobs.get(job_id)
            if job_id
            else next(reversed(self.__jobs.values()), None)
        )

        if job is None:
            return JSONResponse(
                {"error": "Job not found or removed from cache"}, status_code=404
            )
        elif job.status == "done":
            return JSONResponse({"shifts": job.result})
        elif job.status == "failed":
            return JSONResponse({"error": "Job failed"}, status_code=500)
        else:
            return JSONResponse({"status": job.status})
