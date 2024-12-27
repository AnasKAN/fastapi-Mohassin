
import time
import json
import os
from hajj_tafweej_scheduling_optimizer import Tafweej_Scheduling_Optimizer
import pymysql
from datetime import datetime

# Database connection configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "my-app-db.cliaouaicgro.eu-north-1.rds.amazonaws.com"),  
    "user": os.getenv("DB_USER", "admin"),  
    "password": os.getenv("DB_PASSWORD", "204863Wante#"),  
    "database": os.getenv("OPT_DB_NAME", "OptimizationProblemDatabase"), 
    "cursorclass": pymysql.cursors.DictCursor,
}

def connect_to_database():
    """Establish a connection to the database."""
    try:
        print("Attempting to connect to the database...")
        connection = pymysql.connect(**DB_CONFIG)
        print("Database connection successful!")
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def fetch_processing_jobs():
    """Fetch jobs in the 'processing' state."""
    connection = connect_to_database()
    if not connection:
        print("Failed to connect to the database while fetching jobs.")
        return []

    try:
        with connection.cursor() as cursor:
            print("Fetching jobs in the 'processing' state...")
            query = "SELECT * FROM Job WHERE status = 'processing'"
            cursor.execute(query)
            jobs = cursor.fetchall()
            print(f"Fetched {len(jobs)} jobs.")
            return jobs
    except Exception as e:
        print(f"Error fetching jobs: {e}")
        return []
    finally:
        connection.close()


def validate_api_key(api_key):
    """Validate if the given API key exists in the ApiKeys table."""
    connection = connect_to_database()
    if not connection:
        print("Failed to connect to the database while validating API key.")
        return False


    try:
        with connection.cursor() as cursor:
            print(f"Validating API key: {api_key}")
            query = "SELECT 1 FROM ApiKeys WHERE api_key = %s"
            cursor.execute(query, (api_key,))
            is_valid = cursor.fetchone() is not None
            print(f"API key valid: {is_valid}")
            return is_valid
    except Exception as e:
        print(f"Error validating API key: {e}")
        return False
    finally:
        connection.close()

def get_solver_id(optimizer_name):
    """Fetch solver_id from the Solvers table based on optimizer_name."""
    connection = connect_to_database()
    if not connection:
        print("Failed to connect to the database while fetching solver_id.")
        return None

    try:
        with connection.cursor() as cursor:
            query = "SELECT solver_id FROM Solvers WHERE solver_name = %s"
            cursor.execute(query, (optimizer_name,))
            result = cursor.fetchone()
            return result["solver_id"] if result else None
    except Exception as e:
        print(f"Error fetching solver_id: {e}")
        return None
    finally:
        connection.close()

def update_job_status(job_id, status, result_data=None, time_to_solve=None):
    """Update the job status, result data, and time_to_solve in the database."""
    connection = connect_to_database()
    if not connection:
        return

    try:
        with connection.cursor() as cursor:
            query = """
                UPDATE Job
                SET status = %s, result_data = %s, time_to_solve = %s, updated_at = NOW()
                WHERE job_id = %s
            """
            cursor.execute(query, (status, json.dumps(result_data) if result_data else None, time_to_solve, job_id))
        connection.commit()
        print(f"Job {job_id} updated to status '{status}' with time_to_solve = {time_to_solve}.")
    except Exception as e:
        print(f"Error updating job {job_id}: {e}")
    finally:
        connection.close()


def process_job(job):
    """Process a single job using the appropriate optimizer."""
    try:
        input_data = json.loads(job["input_data"])
        api_key = input_data.get("api_key")
        data = input_data.get("data")
        optimizer_name = input_data.get("optimizer_name")

        if not data:
            print(f"Job {job['job_id']} has no data to process.")
            return {"status": "error", "message": "No data provided for processing."}

        # Determine solver_id
        solver_id = job.get("solver_id")
        if not solver_id and optimizer_name:
            solver_id = get_solver_id(optimizer_name)
            if not solver_id:
                return {"status": "error", "message": f"Optimizer '{optimizer_name}' not found."}

        print(f"Processing job {job['job_id']} with solver ID {solver_id}.")
        if solver_id == 1:  # Tafweej Scheduling Optimizer
            optimizer = Tafweej_Scheduling_Optimizer()
            result = optimizer.scheduling_model_corrected(data)

            return {
                "status": "success",
                "result": result
            }

        else:
            print(f"Solver ID {solver_id} is not recognized.")
            return {"status": "error", "message": "Solver not recognized."}

    except Exception as e:
        print(f"Error processing job {job['job_id']}: {e}")
        return {"status": "error", "message": str(e)}

def main():
    # Accept the job_id as a command-line argument
    if len(sys.argv) < 2:
        print("Usage: python hub.py <job_id>")
        return

    job_id = sys.argv[1]
    print(f"Processing job with ID: {job_id}")

    # Fetch and process the job
    connection = connect_to_database()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM Job WHERE job_id = %s AND status = 'processing'", (job_id,))
            job = cursor.fetchone()

            if not job:
                print(f"No job found with ID {job_id} in 'processing' state.")
                return

            # Start timing the job processing
            start_time = time.time()

            # Process the job
            result = process_job(job)

            # End timing the job processing
            end_time = time.time()
            time_to_solve = int(end_time - start_time)

            # Update job status in the database
            if result["status"] == "success":
                update_job_status(job_id, "finished", result, time_to_solve)
            else:
                update_job_status(job_id, "failed", result, None)

    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    main()