import numpy as np
import json
import cv2
import networkx as nx
from queue import PriorityQueue
import matplotlib.pyplot as plt
import detectree as dtr
from scipy.spatial import KDTree

def __plot_overlap__(rect1, rect2, min_distance):
    x1, y1, w1, h1 = rect1
    x2, y2, w2, h2 = rect2

    return not (
        x1 + w1 + min_distance <= x2 or
        x2 + w2 + min_distance <= x1 or
        y1 + h1 + min_distance <= y2 or
        y2 + h2 + min_distance <= y1
    )

def get_contours(mask: np.ndarray) -> np.ndarray:
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return contours

def mask_range(mask: np.ndarray, contour_min_size: int = 1000, range_size: int = 200) -> np.ndarray:
    near_mask = np.zeros_like(mask) # new empty mask
    contours = get_contours(mask)

    # Add radius around contours to mask
    for cnt in contours:
        if cv2.contourArea(cnt) >= contour_min_size:
            cv2.drawContours(near_mask, [cnt], -1, 255, thickness=range_size)

    return near_mask

def get_mask_regions(mask: np.ndarray, min_size: int = 0) -> list:
    # Apply connected components to label each separate area
    num_labels, labels = cv2.connectedComponents(mask)

    # Create a list to store individual masks
    mask_regions = []

    # Generate each mask for the labeled regions (ignore label 0, which is the background)
    for label in range(1, num_labels):
        # Create a new mask for each component
        component_mask = (labels == label).astype(np.uint8)
        
        # Check if the region's size is greater than the minimum size
        if np.sum(component_mask) >= min_size:
            mask_regions.append(component_mask)
    
    return mask_regions

def get_mask_centroid(mask: np.ndarray) -> tuple[int, int]:
    # Calculate moments of the mask
    moments = cv2.moments(mask)

    # Calculate the centroid from the moments (cx, cy)
    if moments["m00"] != 0:  # To avoid division by zero
        cx = int(moments["m10"] / moments["m00"])
        cy = int(moments["m01"] / moments["m00"])
    else:
        # If the area is zero, set centroid to None
        return None
    
    return cx, cy

def get_buildings(sort_priority: bool = True) -> list:
    with open("buildings.json", "r") as f:
        buildings = json.load(f)
    
    if sort_priority:
        # Sorting by priority (descending) and then by size (descending)
        return sorted(
            buildings, 
            key=lambda x: (x["priority"], x["size"][0] * x["size"][1]), 
            reverse=True
            )
    else:
        return buildings

def place_buildings(blueprints: list, amounts: dict[str, int], masks: dict[str, np.ndarray]) -> tuple[list, np.ndarray]:
    # Get buildings from blueprints
    buildings_to_place = []
    for blueprint in blueprints:
        # Place amount of blueprint specified
        for _ in range(amounts[blueprint["name"]]):
            buildings_to_place.append(blueprint)

    # Place buildings
    placed_buildings = []
    building_mask = np.zeros_like(masks["zero"])
    for building in buildings_to_place:
        nametag = building["name"]
        dimensions = building["size"]
        location = building["location"]

        # Get possible location mask
        mask = masks[location]
        centroid = get_mask_centroid(mask)

        # Iterate over the mask
        for y, x in sorted(np.argwhere(mask > 0), key=lambda x: ((x[0] - centroid[0]) ** 2 + (x[1] - centroid[1]) ** 2) ** 0.5):  # Sort by distance to centroid
            rect_width, rect_height = dimensions[0], dimensions[1]

            #Check if rectangles fit within the mask-area
            if (x + rect_width <= mask.shape[1]) and (y + rect_height <= mask.shape[0]):
                if np.all(mask[y:y + rect_height, x:x + rect_width] > 0):
                    new_rect = (x, y, rect_width, rect_height)

                    # Check building collision
                    min_distance = 10
                    if all(not __plot_overlap__(new_rect, placed_building["rect"], min_distance) for placed_building in placed_buildings):
                        placed_buildings.append({"nametag": nametag, "rect": new_rect})
                        building_mask[y:y + rect_height, x:x + rect_width] = 1
                        break
    
    return placed_buildings, building_mask

def overlay_from_masks(img, *masks: np.ndarray) -> None:
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Add each mask with its color to the Overlay
    overlay = img_rgb.copy()
    for mask, color, alpha in masks:
        mask_overlay = img_rgb.copy()
        mask_overlay[mask > 0] = color
        overlay = cv2.addWeighted(overlay, 1 - alpha, mask_overlay, alpha, 0)
        # Blend the overlay with the original image
    overlay = cv2.addWeighted(img_rgb, 0, overlay, 1, 0)

    return overlay

def filter_artifacts(mask: np.ndarray, min_area_threshold: int = 2500) -> np.ndarray:
    contours = get_contours(mask)
    filtered_mask = np.zeros_like(mask)

    for cnt in contours:
        if cv2.contourArea(cnt) >= min_area_threshold:
            cv2.drawContours(filtered_mask, [cnt], -1, 255, thickness=cv2.FILLED)

    return filtered_mask

# Custom Delaunay triangulation function
def custom_delaunay(points):
    edges = set()
    num_points = len(points)
    for i in range(num_points):
        for j in range(i + 1, num_points):
            for k in range(j + 1, num_points):
                pi, pj, pk = points[i], points[j], points[k]
                circumcenter, radius = get_circumcircle(pi, pj, pk)
                if circumcenter is None:
                    continue
                is_valid = True
                for m in range(num_points):
                    if m != i and m != j and m != k:
                        if np.linalg.norm(points[m] - circumcenter) < radius:
                            is_valid = False
                            break
                if is_valid:
                    edges.add((i, j))
                    edges.add((j, k))
                    edges.add((k, i))
    return edges

def get_circumcircle(p1, p2, p3):
    A = np.array([
        [p1[0], p1[1], 1],
        [p2[0], p2[1], 1],
        [p3[0], p3[1], 1]
    ])
    D = np.linalg.det(A)
    if D == 0:
        return None, np.inf
    A1 = np.array([
        [p1[0]**2 + p1[1]**2, p1[1], 1],
        [p2[0]**2 + p2[1]**2, p2[1], 1],
        [p3[0]**2 + p3[1]**2, p3[1], 1]
    ])
    A2 = np.array([
        [p1[0]**2 + p1[1]**2, p1[0], 1],
        [p2[0]**2 + p2[1]**2, p2[0], 1],
        [p3[0]**2 + p3[1]**2, p3[0], 1]
    ])
    A3 = np.array([
        [p1[0]**2 + p1[1]**2, p1[0], p1[1]],
        [p2[0]**2 + p2[1]**2, p2[0], p2[1]],
        [p3[0]**2 + p3[1]**2, p3[0], p3[1]]
    ])
    x = np.linalg.det(A1) / (2 * D)
    y = -np.linalg.det(A2) / (2 * D)
    radius = np.sqrt(np.linalg.det(A3) / D + x**2 + y**2)
    return np.array([x, y]), radius

def building_centers(buildings: list) -> np.ndarray:
    return np.array([(building["rect"][0] + building["rect"][2] // 2, building["rect"][1] + building["rect"][3] // 2) for building in buildings])

def generate_path_tree(buildings: list, max_length: int|None = None) -> list[tuple[tuple]]:
    centers = building_centers(buildings)

    # Generate paths between all centers using Delauney
    edges = custom_delaunay(centers)

    # Create a graph from the edges
    graph = nx.Graph()
    for edge in edges:
        p1, p2 = centers[edge[0]], centers[edge[1]]
        distance = np.linalg.norm(p1 - p2)
        if max_length is None or distance <= max_length:  # Only add edges that are within the max length
            graph.add_edge(edge[0], edge[1], weight=distance)

    # Create minimum spanning tree of graph
    mst: nx.Graph = nx.minimum_spanning_tree(graph)
    
    paths = []
    for edge in mst.edges():
        p1, p2 = centers[edge[0]], centers[edge[1]]
        paths.append((p1, p2))

    return paths

def astar(start: tuple, goal: tuple, masks: dict[str, np.ndarray], cost_multipliers: dict[str, float]) -> list[tuple]|None:
    start, goal = tuple(start), tuple(goal)
    rows, cols = masks["zero"].shape

    # Precompute cost map
    cost_map = np.zeros((rows, cols))
    for name, mask in masks.items():
        cost_map += mask * cost_multipliers[name]

    # Heuristic function: Octile distance
    def heuristic(a, b):
        D, D2 = 1, 1.414  # D for cardinal moves, D2 for diagonal moves
        dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
        return D * (dx + dy) + (D2 - 2 * D) * min(dx, dy)

    # Directions: including diagonals
    directions = [
        (1, 0), (-1, 0), (0, 1), (0, -1),    # cardinal directions
        (1, 1), (1, -1), (-1, 1), (-1, -1)    # diagonal directions
    ]

    # Initialize PriorityQueue
    queue = PriorityQueue()
    queue.put((0, start))  # (cost, position)
    costs = {start: 0}    # Cost from start to each position
    came_from = {start: None}  # For reconstructing path

    while not queue.empty():
        current_cost, current = queue.get()

        # Check if reached the goal
        if current == goal:
            path = []
            while current:
                path.append(current)
                current = came_from[current]
            return path[::-1]  # Return reversed path from start to goal

        # Explore neighbors
        for d in directions:
            neighbor = (current[0] + d[0], current[1] + d[1])

            # Check if the neighbor is within bounds
            if 0 <= neighbor[0] < cols and 0 <= neighbor[1] < rows:
                # Cost to move to neighbor (1 for cardinal, ~1.414 for diagonal)
                move_cost = 1 if d in [(1, 0), (-1, 0), (0, 1), (0, -1)] else 1.414
                # Apply mask multipliers
                move_cost *= cost_map[neighbor[1]][neighbor[0]]
                new_cost = costs[current] + move_cost

                # If the neighbor hasn't been visited or we found a cheaper path
                if neighbor not in costs or new_cost < costs[neighbor]:
                    costs[neighbor] = new_cost
                    priority = new_cost + heuristic(neighbor, goal)
                    queue.put((priority, neighbor))
                    came_from[neighbor] = current

    return None  # No path found if loop completes without returning

def get_connectors_from_centers(p1: np.ndarray, p2: np.ndarray, building_mask: np.ndarray):
    dir_vector = (p1 - p2) / np.linalg.norm(p2 - p1)

    dir_vector = np.round(dir_vector).astype(int)

    # Move points out of building
    while building_mask[p1[1]][p1[0]] > 0:
        p1 -= dir_vector
    while building_mask[p2[1]][p2[0]] > 0:
        p2 += dir_vector

    return p1, p2

def generate_path_points(buildings: list, masks_and_cost_multipliers: dict[str, tuple[np.ndarray, float]], resolution_factor: float = 1, max_distance: int|None = None) -> list[list[tuple]]:
    path_tree = generate_path_tree(buildings, max_length=max_distance)

    masks = {name: scale_mask(masks_and_cost_multipliers[name][0], resolution_factor) for name in masks_and_cost_multipliers}
    cost_multipliers = {name: masks_and_cost_multipliers[name][1] for name in masks_and_cost_multipliers}

    path_points = []
    bridge_points = []
    for p1, p2 in path_tree:
        p1, p2 = get_connectors_from_centers(p1, p2, masks_and_cost_multipliers['buildings'][0])
        p1 = (int(p1[0] * resolution_factor), int(p1[1] * resolution_factor))
        p2 = (int(p2[0] * resolution_factor), int(p2[1] * resolution_factor))
        points = astar(p1, p2, masks=masks, cost_multipliers=cost_multipliers)
        path_points.append([(x // resolution_factor, y // resolution_factor) for x, y in points])
        bridge_points.extend([(x // resolution_factor, y // resolution_factor) for x, y in points if masks['water'][y][x] > 0])
    
    return path_points, bridge_points

def scale_mask(mask: np.ndarray, scale: float) -> np.ndarray:
    new_mask = cv2.resize(mask, (int(mask.shape[1] * scale), int(mask.shape[0] * scale)), interpolation=cv2.INTER_LINEAR)

    return new_mask

def get_mask_exit_point(mask: np.ndarray, direction_vector: np.ndarray, step_size: float = 1.0) -> np.ndarray:
    current_point = np.array(get_mask_centroid(mask))
    direction = np.array(direction_vector) / np.linalg.norm(direction_vector)  # Normalize direction

    while current_point.astype(int) in np.argwhere(mask > 0):
        current_point += step_size * direction

    return current_point  # This point is outside the mask

def get_nearst_point_in_mask(mask: np.ndarray, point: tuple) -> tuple[tuple, float]:
    # Convert mask to a list of coordinates
    mask_points = np.array([(y, x) for y in range(mask.shape[0]) for x in range(mask.shape[1]) if mask[y, x] > 0])

    # Build KD-Tree
    tree = KDTree(mask_points)

    # Find closest point
    distance, index = tree.query(point)
    closest_point = mask_points[index]

    return closest_point, distance

def get_mask_edge_points(mask: np.ndarray) -> list[tuple]:
    # Use Canny edge detection to find the edges
    edges = cv2.Canny(mask.astype(np.uint8) * 255, 100, 200)

    # Get the coordinates of the edge pixels
    edge_points = np.column_stack(np.where(edges > 0))

    return edge_points

if __name__ == "__main__":

    def get_tree_mask(img_path: str, expansion_thickness: int = 2, min_area: int = 10) -> np.ndarray:
        y_pred = dtr.Classifier().predict_img(img_path)
        tree_mask = y_pred.astype(np.uint8)

        contours = get_contours(tree_mask)

        # Draw Contours around vegetation areas based on "expansion-thickness"
        expanded_mask = np.zeros_like(tree_mask) # new mask layer
        for cnt in contours:
            if cv2.contourArea(cnt) >= min_area:
                cv2.fillPoly(expanded_mask, [cnt], 255)

                if expansion_thickness > 0:
                    cv2.drawContours(expanded_mask, [cnt], -1, 255, thickness=expansion_thickness)

        return expanded_mask

    def get_water_mask(img_path: str, min_area_threshold: int = 500, water_kernel_size: int = 12) -> np.ndarray:
        img = cv2.imread(img_path)
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Color Range
        lower_water = np.array([90, 50, 50])
        upper_water = np.array([140, 255, 255])

        mask_water = cv2.inRange(hsv, lower_water, upper_water)

        # Morphological operations (close small gaps in layer)
        water_kernel = np.ones((water_kernel_size, water_kernel_size), np.uint8)
        closed_water_mask = cv2.morphologyEx(mask_water, cv2.MORPH_CLOSE, water_kernel)

        # Find contours in water segments
        contours = get_contours(closed_water_mask)

        # Filter out artifacts (small water areas based on given threshold)
        filtered_water_mask = np.zeros_like(closed_water_mask)
        for cnt in contours:
            if cv2.contourArea(cnt) >= min_area_threshold:
                cv2.drawContours(filtered_water_mask, [cnt], -1, 255, thickness=cv2.FILLED)

        return (filtered_water_mask > 0).astype(np.uint8)

    def get_zero_mask(tree_mask: np.ndarray, water_mask: np.ndarray) -> np.ndarray:
        # Combine tree and water masks to find free areas
        combined_mask = np.logical_or(tree_mask > 0, water_mask > 0).astype(np.uint8)

        # Inverted mask to get free areas
        free_area_mask = (combined_mask == 0).astype(np.uint8)

        # zero_mask =  hf.filter_artifacts(free_area_mask)
        zero_mask = free_area_mask

        return zero_mask


    image_input_path = "./mocking-examples/main2.png"
    
    water_mask = get_water_mask(image_input_path)
    tree_mask = get_tree_mask(image_input_path)
    zero_mask = get_zero_mask(tree_mask, water_mask)

    zones = get_mask_regions(zero_mask, min_size=1000)
    
    fig, axes = plt.subplots(1, 1 + len(zones), figsize=(10, 5))

    axes[0].imshow(zero_mask)
    axes[0].set_title("Zero Mask")

    for i, zone in enumerate(zones):
        axes[i + 1].imshow(zone)
        axes[i + 1].set_title(f"Zone {i + 1}")
    
    plt.tight_layout()
    plt.show()
