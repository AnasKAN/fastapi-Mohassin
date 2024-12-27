
import time
import json
import os
from hajj_tafweej_scheduling_optimizer import Tafweej_Scheduling_Optimizer
import pymysql

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


def update_job_status(job_id, status, result_data=None):
    """Update the job status and result data in the database."""
    connection = connect_to_database()
    if not connection:
        return

    try:
        with connection.cursor() as cursor:
            query = """
                UPDATE Job
                SET status = %s, result_data = %s, updated_at = NOW()
                WHERE job_id = %s
            """
            cursor.execute(query, (status, json.dumps(result_data) if result_data else None, job_id))
        connection.commit()
        print(f"Job {job_id} updated to status '{status}'.")
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

        if not data:
            print(f"Job {job['job_id']} has no data to process.")
            return {"status": "error", "message": "No data provided for processing."}

        print(f"Processing job {job['job_id']} with solver ID {job['solver_id']}.")
        if job["solver_id"] == 1: #change it: 
            optimizer = Tafweej_Scheduling_Optimizer()
            model, r, d = optimizer.scheduling_model_corrected(data)
            
            # Extract solution and visualization
            solution = optimizer.extract_solution_row(model, r, d, input_data=data)
            visualization = optimizer.visualize_solution(model, r, d, input_data=data)

            return {
                "status": "success",
                "model_status": model.status,
                "decision_variables": solution["group_schedules"],
                "visualization": visualization,
            }
        #elif ==2: #bottleneck sequential process
        #make app.py endpoint startprocess
        #comes from the user. worker for every request
        #don't hardcode adding solvers.
        #make it return dict

        #scalability of the solver using Dr. Thamir's license

        #first deploy the fastapi at a seperate heroku app

        #fastapi should deploy a worker for every request.

        #see how many available threads for heroku

        #after it works change the ui for all, montioring should have a table, and a new column of how much the process took to finish

        #should make the if else routing statements generic somehow when someone adds a new solver it can be ready to accept data instead of using hard coded if else statements

        #finish grad project report with all the necessary diagrams etc,,,



        else:
            print(f"Solver ID {job['solver_id']} is not recognized.")
            return {"status": "error", "message": "Solver not recognized."}

    except Exception as e:
        print(f"Error processing job {job['job_id']}: {e}")
        return {"status": "error", "message": str(e)}

def main():
    print("Hub is running and monitoring for new jobs...")
    try:
        while True:
            print("Checking for jobs...")
            jobs = fetch_processing_jobs()
            if not jobs:
                print("No jobs in 'processing' state. Retrying in 5 seconds...")
                time.sleep(5)
                continue

            for job in jobs:
                print(f"Processing job ID {job['job_id']}...")
                # Validate the API key
                input_data = json.loads(job["input_data"])
                api_key = input_data.get("api_key")

                if not validate_api_key(api_key):
                    print(f"Invalid API key for job {job['job_id']}. Marking as 'failed'.")
                    update_job_status(job["job_id"], "failed", {"error": "Invalid API key"})
                    continue

                # Process the job
                result = process_job(job)

                # Update the database
                if result["status"] == "success":
                    update_job_status(job["job_id"], "finished", result)
                else:
                    update_job_status(job["job_id"], "failed", result)

            # Wait before checking for new jobs
            time.sleep(5)

    except KeyboardInterrupt:
        print("Shutting down the hub...")

if __name__ == "__main__":
    main()
