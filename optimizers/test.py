import json

import json
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np

def visualize_heatmap(file_path):
    """Visualize the heatmap data from a JSON result file."""
    try:
        # Load the JSON file
        with open(file_path, "r") as file:
            result_data = json.load(file)

        # Extract heatmap data from the JSON
        visualization = result_data.get("visualization", {})
        heatmap_data = visualization.get("heatmap_data")
        segments = visualization.get("segments")
        time_ticks = visualization.get("time_ticks")

        if not heatmap_data or not segments or not time_ticks:
            print("Heatmap data is missing or incomplete.")
            return

        # Convert heatmap data to a NumPy array for visualization
        heatmap_array = np.array(heatmap_data)

        # Create the heatmap
        plt.figure(figsize=(10, 6))
        sns.heatmap(heatmap_array, annot=True, cmap="YlGnBu", cbar=True, linewidths=0.5, fmt="g")

        # Set labels and titles
        plt.xlabel("Time Ticks")
        plt.ylabel("Segments")
        plt.title("Segment Occupancy Over Time (Segments vs. Ticks)")

        # Customize ticks
        plt.xticks(ticks=np.arange(len(time_ticks)) + 0.5, labels=time_ticks)
        plt.yticks(ticks=np.arange(len(segments)) + 0.5, labels=segments)

        # Show the heatmap
        plt.show()

    except FileNotFoundError:
        print(f"Error: File '{file_path}' not found.")
    except json.JSONDecodeError:
        print(f"Error: File '{file_path}' is not a valid JSON file.")



if __name__ == "__main__":
    # Specify the path to your result file
    file_path = r"C:\Users\An\Downloads\result_job_33.json"
    visualize_heatmap(file_path)
