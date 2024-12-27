from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict
import uuid
import pymysql
from typing import Optional
from datetime import datetime, timedelta
import json

app = FastAPI()

@app.middleware("http")
async def log_exceptions(request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        print(f"Exception occurred: {e}")  #log the exception
        raise

#db connection configuration
def get_db_connection():
    return pymysql.connect(
        host="my-app-db.cliaouaicgro.eu-north-1.rds.amazonaws.com",
        user="admin",
        password="204863Wante#",
        database="OptimizationProblemDatabase",
        cursorclass=pymysql.cursors.DictCursor
    )

class JobRequest(BaseModel):
    optimizer_id: Optional[int] = None
    optimizer_name: Optional[str] = None
    data: Dict
#validate api key
async def validate_api_key(api_key: str):
    connection = get_db_connection()
    print(f"Validating API key: {api_key}")  
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 1 FROM ApiKeys 
                WHERE api_key = %s AND user_id != 0 AND key_expiration_date >= CURDATE()
                """,
                (api_key,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=401, detail="Invalid or expired API Key")
    finally:
        connection.close()


# Routes
@app.post("/generate-key")
def generate_key(user_id: int = 0):
    print(f"Generating key for user_id: {user_id}")
    connection = get_db_connection()
    new_key = f"API-{uuid.uuid4().hex[:16].upper()}"  
    instantiating_date = datetime.now().date()  
    expiration_date = instantiating_date + timedelta(days=60)

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO ApiKeys (api_key, user_id, key_instantiating_date, key_expiration_date)
                VALUES (%s, %s, %s, %s)
                """,
                (new_key, user_id, instantiating_date, expiration_date),
            )
            connection.commit()
    finally:
        connection.close()

    print(f"Generated API key: {new_key}")
    return {
        "api_key": new_key,
        "key_instantiating_date": instantiating_date.isoformat(),
        "key_expiration_date": expiration_date.isoformat(),
    }



#######HERE THE JOB ID GENERATION IS DIFFERENT ONLY!
# @app.post("/submit-job")
# def submit_job(job_request: JobRequest, api_key: str = Depends(validate_api_key)):
#     print(f"Received job submission: {job_request}")  # Debug log
#     print(f"API key: {api_key}")  # Debug log
#     connection = get_db_connection()
#     job_id = str(uuid.uuid4())
#     try:
#         with connection.cursor() as cursor:
#             query = """
#                 INSERT INTO Job (user_id, solver_id, input_data, status, created_at)
#                 VALUES (%s, %s, %s, %s, NOW())
#             """
#             print(f"Executing query: {query}")  # Debug log
#             cursor.execute(
#                 query,
#                 (0, job_request.optimizer_id, json.dumps(job_request.data), "processing"),  # Convert data to JSON
#             )
#             connection.commit()
#     except Exception as e:
#         print(f"Database error: {e}")  # Debug log
#         raise HTTPException(status_code=500, detail="Database error")
#     finally:
#         connection.close()

#     print(f"Job submitted successfully: {job_id}")  # Debug log
#     return {"job_id": job_id}



@app.post("/submit-job")
def submit_job(job_request: JobRequest, api_key: str = Depends(validate_api_key)):
    print(f"Received job submission: {job_request}")  # Debug log
    print(f"API key: {api_key}")  # Debug log

    if not job_request.optimizer_id and not job_request.optimizer_name:
        raise HTTPException(status_code=400, detail="Either optimizer_id or optimizer_name must be provided.")

    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            # Determine solver_id from optimizer_name if needed
            solver_id = job_request.optimizer_id
            if job_request.optimizer_name:
                cursor.execute(
                    "SELECT solver_id FROM Solvers WHERE solver_name = %s",
                    (job_request.optimizer_name,)
                )
                solver = cursor.fetchone()
                if not solver:
                    raise HTTPException(status_code=404, detail="Optimizer name not found.")
                solver_id = solver["solver_id"]

            query = """
                INSERT INTO Job (user_id, solver_id, input_data, status, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """
            print(f"Executing query: {query}")  # Debug log
            cursor.execute(
                query,
                (0, solver_id, json.dumps(job_request.data), "processing")
            )
            job_id = cursor.lastrowid  # Use the database's auto-generated ID
            connection.commit()
    except Exception as e:
        print(f"Database error: {e}")  # Debug log
        raise HTTPException(status_code=500, detail="Database error")
    finally:
        connection.close()

    print(f"Job submitted successfully: {job_id}")  # Debug log
    return {"job_id": job_id}


@app.get("/job-result/{job_id}")
def get_job_result(job_id: str, api_key: str = Depends(validate_api_key)):
    """Fetch the result of a job."""
    connection = get_db_connection()
    print(f"Fetching job result for job_id={job_id}")  # Debug log
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM Job WHERE job_id = %s", (job_id,))
            job = cursor.fetchone()
            print(f"Job fetched: {job}")  # Debug log
            if not job:
                raise HTTPException(status_code=404, detail="Job not found")

            # Update job status and time_to_solve if processing
            if job["status"] == "processing":
                result_data = {"status": "success", "solution": "Optimal solution for the given data"}
                time_to_solve = 10  # Mock processing time for now

                # Update the database with the results
                cursor.execute(
                    """
                    UPDATE Job
                    SET status = %s, result_data = %s, 
                        time_to_solve = TIMESTAMPDIFF(SECOND, created_at, NOW()),
                        updated_at = NOW()
                    WHERE job_id = %s
                    """,
                    ("finished", json.dumps(result_data), job_id)
                )
                connection.commit()

                # Update the job object to include the changes
                job["status"] = "finished"
                job["result_data"] = result_data
                job["time_to_solve"] = time_to_solve

            return {
                "job_id": job["job_id"],
                "user_id": job["user_id"],
                "solver_id": job["solver_id"],
                "input_data": job["input_data"],
                "result_data": job["result_data"],
                "status": job["status"],
                "time_to_solve": job["time_to_solve"],
                "created_at": job["created_at"],
                "updated_at": job["updated_at"]
            }
    finally:
        connection.close()


@app.get("/optimizers")
def list_optimizers(api_key: str = Depends(validate_api_key)):
    """List available optimizers."""
    connection = get_db_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM Solvers")
            optimizers = cursor.fetchall()
            if not optimizers:
                raise HTTPException(status_code=404, detail="No optimizers found")
            return optimizers
    finally:
        connection.close()



# Run the app using uvicorn (command: uvicorn app:app --reload)