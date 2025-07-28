''' Function to test the path imnport '''

import os
import sys

# Define the path to the custom libraries
path_to_lib = 'C:/Users/fys-lab-ivs/Documents/Git/NottControl/NOTTControl/script/lib/'

# Check if the path exists and list its contents
if os.path.exists(path_to_lib):
    print("Path exists")
    print("Directory contents:", os.listdir(path_to_lib))
else:
    print("Path does not exist")

# Add the path to sys.path
sys.path.append(path_to_lib)
print("Updated sys.path:", sys.path)

# Attempt to import the modules and call the function
try:
    from nott_math import compute_mean_sampling
    print("Module imported successfully")
    
    # Example vector to test the function
    test_vector = [1, 3, 5, 7, 9, 11]
    
    # Call the function with the test vector
    mean_fs = compute_mean_sampling(test_vector)
    print(f"Mean sampling frequency: {mean_fs}")
except ImportError as e:
    print(f"ImportError: {e}")
except Exception as e:
    print(f"An error occurred: {e}")
