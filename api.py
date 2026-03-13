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


class Week(BaseModel):
    start: str
    end: str


class ScheduleRequest(BaseModel):
    timeout: int
    course_name: str
    year: list[int]
    week: Week


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
            config = {
                "timeout": 1,
                "course_name": "Licenciatura em Engenharia Informática",
                "year": [1, 2, 3],
                "week": {
                    "start": "2026-09-15",
                    "end": "2026-10-01",
                },
            }

        self.status = "running"
        try:
            scraper = Scraper(config)
            self.result = [shift.to_dict() for shift in scraper.shifts]
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
            payload = json.loads(body) if body else None
            data = ScheduleRequest.model_validate(payload) if payload else None
        except (json.JSONDecodeError, ValidationError) as e:
            return JSONResponse({"error": str(e)}, status_code=422)

        try:
            job_id = uuid.uuid4()
            job = Job(job_id)
            self.__jobs[job_id] = job
            self.__executor.submit(job.run, data.model_dump() if data else None)

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
