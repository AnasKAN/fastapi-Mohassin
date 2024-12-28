import gurobipy as gp
from gurobipy import GRB
from IPython.display import Image
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List, Tuple, Union
import time
import random
import pickle

class Tafweej_Scheduling_Optimizer:
    #Model
    @staticmethod
    def optimize(input_data: Tuple[List[int],
                                    List[List[int]],
                                    int,
                                    List[List[int]],
                                    List[int]]
                ) -> Tuple[gp.Model, gp.tupledict, gp.tupledict]:

        group_sizes, starting_segments, num_time, segments_connections, road_capacities = input_data

        num_groups = len(group_sizes)
        num_segs = len(segments_connections)

        m = gp.Model("schedule2")

        # Presence variables: r[i,j,k] - group i is in segment k at time j
        r = m.addVars(num_groups, num_time, num_segs, lb=0, vtype=GRB.BINARY, name='group_presence_at_segment_at_a_tick')

        # Dispatch variables: d[i,j] - group i is dispatched at time j
        d = m.addVars(num_groups, num_time, vtype=GRB.BINARY, name="dispatch")

        # Objective: Minimize the sum of differences between road capacities and group presence
        m.setObjective(
            gp.quicksum(road_capacities[k] - gp.quicksum(r[i, j, k] * group_sizes[i] for i in range(num_groups))
                        for j in range(num_time) for k in range(num_segs)),
            sense=GRB.MINIMIZE)

        # Constraint 1: Capacity constraint - do not exceed road capacities
        for j in range(num_time):
            for k in range(num_segs):
                m.addConstr(gp.quicksum(r[i, j, k] * group_sizes[i] for i in range(num_groups)) <= road_capacities[k],
                            f"capacity_constraint_{j}_{k}")

        # Constraint 2: Each group can be assigned to at most one segment at any time
        for i in range(num_groups):
            for j in range(num_time):
                m.addConstr(gp.quicksum(r[i, j, k] for k in range(num_segs)) <= 1,
                            f"group_assignment_constraint_{i}_{j}")

        # Constraint 3: Each group is dispatched exactly once
        for i in range(num_groups):
            m.addConstr(gp.quicksum(d[i, j] for j in range(num_time)) == 1,
                        name=f"group_{i+1}_single_start_tick")

        # Optimize to initialize d[i,j] for dispatch decisions
        m.optimize()

        # Constraint 4: If a group is dispatched, it must be placed in a valid starting segment at that time
        for i in range(num_groups):
            for j in range(num_time):
                if d[i, j].X == 1:  # Once the group is dispatched
                    for s in range(num_segs):
                        if starting_segments[i][s] == 1:
                            # Group i is dispatched at its starting segment at time j
                            m.addConstr(r[i, j, s] == 1,
                                        name=f"group_{i+1}_dispatch_at_correct_segment_at_J{j+1}")
                        else:
                            # Group i is not in any other segment when dispatched
                            m.addConstr(r[i, j, s] == 0,
                                        name=f"group_{i+1}_not_dispatch_at_wrong_segment_at_J{j+1}")

        # Constraint 5: Groups must follow valid segment connections for forward movement
        for i in range(num_groups):
            for j in range(num_time - 1):
                for s1 in range(num_segs):
                    for s2 in range(num_segs):
                        if segments_connections[s1][s2] == 1:
                            m.addConstr(
                                r[i, j + 1, s2] >= r[i, j, s1],  # Move forward to next connected segment
                                name=f"group_{i+1}_must_move_forward_from_{s1+1}_to_{s2+1}_at_tick_{j+1}_to_{j+2}"
                            )

        # Constraint 6: Groups cannot return to previous segments once they move forward
        for i in range(num_groups):
            for j in range(num_time - 1):
                for s1 in range(num_segs):
                    for s2 in range(num_segs):
                        if s2 < s1:  # Prevent backward movement
                            m.addConstr(
                                r[i, j, s1] + r[i, j + 1, s2] <= 1,
                                name=f"group_{i+1}_no_backward_move_from_{s1+1}_to_{s2+1}_at_tick_{j+1}_to_{j+2}"
                            )

        #constraint 7: Once a group reaches the final segment, it must remain there for all future ticks
        final_segment = num_segs - 1
        for i in range(num_groups):
            for j in range(num_time - 1):
                m.addConstr(
                    r[i, j, final_segment] <= r[i, j + 1, final_segment],  #remain in the final segment
                    name=f"group_{i+1}_remain_in_final_segment_after_reaching_at_{j+1}"
                )

        # Optimize the model to find the solution
        m.optimize()

        return m, r, d

    #Helper functions
    @staticmethod
    def print_solution(model: gp.Model,
                    *decision: gp.tupledict,
                    input_data: Tuple[List[int], List[List[int]], int, List[List[int]], List[int]]
                    )-> None:

        group_sizes, starting_segments, num_ticks, segments_connections, capacities = input_data
        final_segment = len(segments_connections) - 1  # The final segment (dummy)

        if model.status == GRB.OPTIMAL:
            print("Optimal solution found:\n")
            for i in range(len(group_sizes)):  # Iterate over groups
                reached_final_segment = False  # Track if the group reached the final segment
                for j in range(num_ticks):  # Iterate over ticks
                    if reached_final_segment:
                        break  # Stop printing if the group has already reached the final segment

                    for k in range(len(segments_connections)):  # Iterate over segments
                        if decision[0][i, j, k].X == 1:
                            print(f"Group {i+1} at tick {j+1} in segment {k+1}: {decision[0][i, j, k].X * group_sizes[i]}")
                            print(f'd[{i+1},{j+1}] = {decision[1][i, j].X}')

                            # Check if the group has reached the final segment
                            if k == final_segment:
                                reached_final_segment = True  # Mark that the group has reached the final segment
                                break  # Stop printing for this group

        else:
            print("No optimal solution found.")

        if model.status == GRB.INFEASIBLE:
            model.computeIIS()
            model.write("infeasible_model1.ilp")
            print("Infeasibility found. Check 'infeasible_model.ilp' for the conflicting constraints.")
    
    @staticmethod
    def print_solution_row(model: gp.Model,
                    *decision: gp.tupledict,
                    input_data: Tuple[List[int], List[List[int]], int, List[List[int]], List[int]]
                    ) -> None:

        group_sizes, starting_segments, num_ticks, segments_connections, capacities = input_data
        final_segment = len(segments_connections) - 1  # The final segment (dummy)

        if model.status == GRB.OPTIMAL:
            print("Optimal solution found:\n")
            for i in range(len(group_sizes)):  # Iterate over groups
                schedule = []  # Collect the schedule for each group
                reached_final_segment = False  # Track if the group reached the final segment

                for j in range(num_ticks):  # Iterate over ticks
                    if reached_final_segment:
                        break  # Stop processing if the group has already reached the final segment

                    for k in range(len(segments_connections)):  # Iterate over segments
                        if decision[0][i, j, k].X == 1:
                            # Append the tick and segment to the group's schedule
                            schedule.append(f"tick {j+1} at segment {k+1}")

                            # Check if the group has reached the final segment
                            if k == final_segment:
                                reached_final_segment = True  # Mark that the group has reached the final segment
                                break  # Stop iterating over segments for this group

                # Print the group's schedule
                print(f"Group {i+1} schedule: [{', '.join(schedule)}]")

        else:
            print("No optimal solution found.")

        if model.status == GRB.INFEASIBLE:
            model.computeIIS()
            model.write("infeasible_model.ilp")
            print("Infeasibility found. Check 'infeasible_model.ilp' for the conflicting constraints.")

    @staticmethod
    def visualize(model: gp.Model,
              *decision: gp.tupledict,
              input_data: Tuple[List[int], List[List[int]], int, List[List[int]], List[int]]
              )-> None:

        group_sizes, starting_segments, num_ticks, segments_connections, capacities = input_data

        num_segs = len(segments_connections)
        num_groups = len(group_sizes)
        num_time = num_ticks

        occupancy = np.zeros((num_segs, num_time))

        #populate occupancy matrix
        if model.status == GRB.OPTIMAL:
            for i in range(num_groups):
                for j in range(num_time):
                    for k in range(num_segs):
                        if decision[0][i, j, k].X == 1:
                            occupancy[k, j] += group_sizes[i]
        else:
            print("No optimal solution found.")
            return

        plt.figure(figsize=(10, 6))
        sns.heatmap(occupancy, annot=True, cmap="YlGnBu", cbar=True, linewidths=.5, fmt="g")

        plt.xlabel("Time Ticks")
        plt.ylabel("Segments")
        plt.title("Segment Occupancy Over Time (Segments vs Ticks)")

        plt.xticks(ticks=np.arange(num_time) + 0.5, labels=np.arange(1, num_time + 1))
        plt.yticks(ticks=np.arange(num_segs) + 0.5, labels=np.arange(1, num_segs + 1))

        plt.show()

    @staticmethod
    def extract_solution_row(model: gp.Model,
                             *decision: gp.tupledict,
                             input_data: Tuple[List[int], List[List[int]], int, List[List[int]], List[int]]
                             ) -> dict:
        """
        Extract the solution row for each group in JSON format.
        """
        group_sizes, starting_segments, num_ticks, segments_connections, capacities = input_data
        final_segment = len(segments_connections) - 1  # The final segment (dummy)

        result = {
            "status": "Optimal solution found" if model.status == GRB.OPTIMAL else "No optimal solution found",
            "group_schedules": []
        }

        if model.status == GRB.OPTIMAL:
            for i in range(len(group_sizes)):  # Iterate over groups
                schedule = []  # Collect the schedule for each group
                reached_final_segment = False  # Track if the group reached the final segment

                for j in range(num_ticks):  # Iterate over ticks
                    if reached_final_segment:
                        break  # Stop processing if the group has already reached the final segment

                    for k in range(len(segments_connections)):  # Iterate over segments
                        if decision[0][i, j, k].X == 1:
                            # Append the tick and segment to the group's schedule
                            schedule.append({"tick": j + 1, "segment": k + 1})

                            # Check if the group has reached the final segment
                            if k == final_segment:
                                reached_final_segment = True  # Mark that the group has reached the final segment
                                break  # Stop iterating over segments for this group

                # Append the group's schedule to the result
                result["group_schedules"].append({"group": i + 1, "schedule": schedule})

        if model.status == GRB.INFEASIBLE:
            model.computeIIS()
            model.write("infeasible_model.ilp")
            result["status"] = "Infeasibility found. Check 'infeasible_model.ilp' for details."

        return result

    @staticmethod
    def visualize_solution(model: gp.Model,
                        *decision: gp.tupledict,
                        input_data: Tuple[List[int], List[List[int]], int, List[List[int]], List[int]]
                        ) -> dict:
        """
        Generate the heatmap data for visualization without displaying the plot.
        """
        group_sizes, starting_segments, num_ticks, segments_connections, capacities = input_data

        num_segs = len(segments_connections)
        num_groups = len(group_sizes)
        num_time = num_ticks

        occupancy = np.zeros((num_segs, num_time))

        # Populate occupancy matrix
        if model.status == GRB.OPTIMAL:
            for i in range(num_groups):
                for j in range(num_time):
                    for k in range(num_segs):
                        if decision[0][i, j, k].X == 1:
                            occupancy[k, j] += group_sizes[i]
        else:
            print("No optimal solution found.")
            return {"status": "No optimal solution found"}

        # Prepare data for heatmap
        heatmap_data = occupancy.tolist()

        # Return the heatmap data in JSON-serializable format
        return {
            "status": "Optimal solution found",
            "heatmap_data": heatmap_data,
            "time_ticks": list(range(1, num_time + 1)),
            "segments": list(range(1, num_segs + 1))
        }

