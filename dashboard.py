import cv2
import os
import numpy as np
import tkinter as tk
import matplotlib.pyplot as plt
import helper_functions as hf
from area_mapping import mask_deployment, get_tree_mask, get_water_mask
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.image as mpimg
from tkinter import ttk
from tkinter import colorchooser

def on_hover(event):
    # Get the index of the item under the mouse cursor
    hovered_index = image_listing.nearest(event.y)
    
    if 0 <= hovered_index < len(image_files):  # Ensure the index is valid
        hovered_image = image_files[hovered_index]
        update_plot(loading=False, only_image=True, image_name=hovered_image)

# Function to update the plot based on the image
def update_plot(loading=False, only_image: bool = False, image_name: str = None):
    if not only_image:
        overlay = img.copy()
        alpha: float = alpha_var.get()

        global mask_colors

        active_masks = []

        def hex_to_rgb(hex_color):
            """
            Converts a hex string to an RGB tuple.
            :param hex_color: A hex color string in the format '#RRGGBB'.
            :return: A tuple with three integers (R, G, B), each in the range 0-255.
            """
            hex_color = hex_color.lstrip("#")  # Remove the '#' if it exists
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        if coast_var.get():
            active_masks.append((coast_mask, hex_to_rgb(mask_colors["coast_color"]), alpha))

        if inland_var.get():
            active_masks.append((inland_mask, hex_to_rgb(mask_colors["inland_color"]), alpha))

        if forest_edge_var.get():
            active_masks.append((forest_edge_mask, hex_to_rgb(mask_colors["forest_edge_color"]), alpha))

        if tree_var.get():
            active_masks.append((tree_mask, hex_to_rgb(mask_colors["tree_color"]), alpha))

        if water_var.get():
            active_masks.append((water_mask, hex_to_rgb(mask_colors["water_color"]), alpha))
        
        overlay = hf.overlay_from_masks(overlay, *active_masks)
    else:
        img_path = os.path.join("./mocking_examples", image_name)
        preview_img = cv2.imread(img_path)
        overlay = cv2.cvtColor(preview_img, cv2.COLOR_BGR2RGB)

    # Update matplotlib plot
    ax.clear()

    # Show "Loading..." text when loading flag is set
    ax.text(0.5, 0.5, 'Loading...' if loading else "", color='black', fontsize=18, ha='center', va='center', transform=ax.transAxes)

    ax.imshow(overlay)

    if not only_image:

        x_limits = ax.get_xlim()
        y_limits = ax.get_ylim()

        # Display paths if path layer is enabled
        if path_var.get():
            for path_points in paths_points:
                if path_points is not None:
                    for i, point in enumerate(path_points):
                        if i > 0:
                            x1, y1 = path_points[i - 1]
                            x2, y2 = point
                            line = plt.Line2D(
                                [x1, x2], [y1, y2],
                                linewidth=3,
                                color=(0.7, 0.7, 0.7) if point not in bridge_points else (0.8, 0.6, 0.4), 
                                zorder=1
                            )
                            ax.add_line(line)  # Add the path line

        # Display buildings if building layer is enabled
        if building_var.get():
            for building in buildings:
                x, y, w, h = building["rect"]
                if not building_icons.get():
                    rect = plt.Rectangle(
                        (x, y), w, h,
                        linewidth=1, edgecolor="white", facecolor="none", 
                        zorder=2
                    )
                    ax.add_patch(rect)  # Draw the building rectangle
                    ax.text(
                        x + w / 2, y - 5,
                        building["nametag"],
                        color="white", fontsize=6, ha="center", 
                        zorder=3
                    )
                else:
                    try:
                        icon = mpimg.imread(f"./icons/{'_'.join(building['nametag'].lower().split())}.png")[::-1]
                    except FileNotFoundError:
                        icon = mpimg.imread(f"./icons/wip.png")[::-1]
                    ax.imshow(
                        icon,
                        extent=[x + w / 2 - 15, x + w / 2 + 15, y + h / 2 - 15, y + h / 2 + 15],  # Position and size of the icon
                        aspect='equal',  # Scale image to fit the extent
                        zorder=2
                    )
        
        ax.set_xlim(x_limits)
        ax.set_ylim(y_limits)

    canvas.draw()

# Function to load a new image based on the image listing
def load_image(event=None):
    update_plot(loading=True)  # Show "Loading..." text before loading masks

    global img, coast_mask, inland_mask, forest_edge_mask, tree_mask, water_mask, buildings, paths_points, bridge_points
    
    # Delay loading and calculating masks to ensure the "Loading..." text is shown
    def update_masks():
        global img, coast_mask, inland_mask, forest_edge_mask, tree_mask, water_mask, buildings, paths_points, bridge_points
        
        # Load the selected image
        if not image_listing.get(image_listing.curselection()[0]):
            img_path = os.path.join("./mocking_examples", image_files[0])
            img = cv2.imread(img_path)
        else:
            img_path = os.path.join("./mocking_examples", image_listing.get(image_listing.curselection()[0]))
            img = cv2.imread(img_path)

        # Calculate masks for the new image
        coast_mask, inland_mask, forest_edge_mask, tree_mask, water_mask, buildings, paths_points, bridge_points = mask_deployment(
            get_tree_mask(img_path), get_water_mask(img_path), (cost_1.get(), cost_2.get(), cost_3.get(), cost_4.get())
        )
        
        # Update plot with new masks
        update_plot(loading=False)  # Remove "Loading..." text and show new masks

    # Delay mask loading using `after` to ensure the text is shown
    root.after(100, update_masks)

# Create Tkinter main window
root = tk.Tk()
root.title("Mask Dashboard")
root.attributes('-fullscreen', True)

style = ttk.Style()

darker_bg = "#1f1f1f"
dark_bg = "#2e2e2e"
light_bg = "#3a3a3a"
text_color = "#828282"
highlight_color = "#5a5a5a"

# Create a Canvas widget to hold the sidebar and make it scrollable
sidebar_canvas_left = tk.Canvas(root, width=200, bg=darker_bg, border=0, highlightthickness=0)
sidebar_canvas_left.pack(side=tk.LEFT, fill=tk.Y)

# Create a Canvas widget for the image selection/preview on the right
sidebar_canvas_right = tk.Canvas(root, width=200, bg=darker_bg, border=0, highlightthickness=0)
sidebar_canvas_right.pack(side=tk.RIGHT, fill=tk.Y)

# Configure the scrollbar style
style.configure(
    "Dark.Vertical.TScrollbar",
    gripcount=0,
    background=dark_bg,  # Scrollbar background
    troughcolor=dark_bg,  # Background of the trough
    bordercolor=dark_bg,  # Border color
    arrowcolor=dark_bg,  # Color of the arrows
)

# Add a scrollbar to the Canvas
scrollbar_left = ttk.Scrollbar(root, orient="vertical", command=sidebar_canvas_left.yview, style="Dark.Vertical.TScrollbar")
scrollbar_left.pack(side=tk.LEFT, fill="y")

# Create a frame inside the Canvas to hold sidebar content
sidebar_left = tk.Frame(sidebar_canvas_left, width=200, bg=darker_bg)
sidebar_left.bind(
    "<Configure>",
    lambda e: sidebar_canvas_left.configure(scrollregion=sidebar_canvas_left.bbox("all"))
)

# Place the frame inside the Canvas
sidebar_canvas_left.create_window((0, 0), window=sidebar_left, anchor="nw")
sidebar_canvas_left.configure(yscrollcommand=scrollbar_left.set)

# Function to enable scrolling with the mouse wheel
def on_mouse_wheel(event):
    # Adjust scroll amount for different platforms
    if event.num == 4 or event.delta > 0:
        sidebar_canvas_left.yview_scroll(-1, "units")
    elif event.num == 5 or event.delta < 0:
        sidebar_canvas_left.yview_scroll(1, "units")

# Bind mouse wheel event for Windows and MacOS
sidebar_canvas_left.bind_all("<MouseWheel>", on_mouse_wheel)

sidebar_canvas_right.bind_all("<MouseWheel>", on_mouse_wheel)

# Bind mouse wheel event for Linux (uses Button-4 and Button-5)
sidebar_canvas_left.bind_all("<Button-4>", on_mouse_wheel)
sidebar_canvas_left.bind_all("<Button-5>", on_mouse_wheel)

# Variables for masks
coast_var = tk.BooleanVar(value=True)
inland_var = tk.BooleanVar(value=True)
forest_edge_var = tk.BooleanVar(value=True)
tree_var = tk.BooleanVar(value=True)
water_var = tk.BooleanVar(value=True)
building_var = tk.BooleanVar(value=True)
path_var = tk.BooleanVar(value=True)

# Checkbox Style
style.configure(
    "Dark.TCheckbutton",
    background=darker_bg,
    foreground=text_color,
    font=("Arial", 10),
    indicatorcolor=light_bg,
    indicatormargin=5,
    indicatordiameter=15,
)

# Checkbox Hover Style
style.map(
    "Dark.TCheckbutton",
    background=[("active", darker_bg)],
    indicatorcolor=[("active", light_bg), ("!active", darker_bg)],
)

# Label Style
style.configure(
    "Dark.TLabel",
    background=darker_bg,
    foreground=text_color,
    font=("Arial", 12, "bold")
)

# Label Style
style.configure(
    "Dark_.TLabel",
    background=darker_bg,
    foreground=text_color,
    font=("Arial", 10)
)

# Title Label RIGHT
ttk.Label(sidebar_canvas_right, text="Select Image", style="Dark.TLabel").pack(anchor="w", padx=5, pady=(10, 5))

image_files = [f for f in os.listdir("./mocking_examples") if f.endswith(".png")]

# Dropdown menu for selecting an image RIGHT
image_listing = tk.Listbox(
    sidebar_canvas_right, 
    height=10, 
    bg=dark_bg, 
    fg=text_color, 
    relief="flat",
    font=("Arial", 10), 
    highlightthickness=0
)
image_listing.pack(padx=10, pady=(5, 10))

# Items in die Listbox einfügen
for image_file in image_files:
    image_listing.insert(tk.END, image_file)

# Bind für Mouseover und Leave-Events
image_listing.bind("<Motion>", lambda event: on_hover(event))
image_listing.bind("<Leave>", lambda event: update_plot(loading=False))
image_listing.bind("<<ListboxSelect>>", load_image)
image_listing.selection_set(0)

# Labels and checkbuttons for masks
ttk.Label(sidebar_left, text="Toggle Layers", style="Dark.TLabel").pack(anchor="w", padx=10, pady=5)

ttk.Checkbutton(sidebar_left, text="Coast Mask", variable=coast_var, style="Dark.TCheckbutton", command=update_plot).pack(anchor="w", padx=10, pady=5)
ttk.Checkbutton(sidebar_left, text="Inland Mask", variable=inland_var, style="Dark.TCheckbutton", command=update_plot).pack(anchor="w", padx=10, pady=5)
ttk.Checkbutton(sidebar_left, text="Forest Edge Mask", variable=forest_edge_var, style="Dark.TCheckbutton", command=update_plot).pack(anchor="w", padx=10, pady=5)
ttk.Checkbutton(sidebar_left, text="Tree Mask", variable=tree_var, style="Dark.TCheckbutton", command=update_plot).pack(anchor="w", padx=10, pady=5)
ttk.Checkbutton(sidebar_left, text="Water Mask", variable=water_var, style="Dark.TCheckbutton", command=update_plot).pack(anchor="w", padx=10, pady=5)
ttk.Checkbutton(sidebar_left, text="Buildings", variable=building_var, style="Dark.TCheckbutton", command=update_plot).pack(anchor="w", padx=10, pady=5)
ttk.Checkbutton(sidebar_left, text="Paths", variable=path_var, style="Dark.TCheckbutton", command=update_plot).pack(anchor="w", padx=10, pady=5)

# Splitter
canvas = tk.Canvas(sidebar_left, width=230, height=1, bg="gray", bd=0, highlightthickness=0)
canvas.pack(padx=10, pady=10)

# Title Label
ttk.Label(sidebar_left, text="Adjust Alpha", style="Dark.TLabel").pack(anchor="w", padx=10, pady=5)

# Transparency Adjustment Slider
alpha_var = tk.DoubleVar(value=0.35)  # Default alpha value
alpha_slider = ttk.Scale(
    sidebar_left, from_=0.0, to=1.0, orient="horizontal", variable=alpha_var,
    style="Horizontal.TScale", command=lambda val: update_plot()
)
alpha_slider.pack(anchor="w", padx=10, pady=5)

# Mask color customization
ttk.Label(sidebar_left, text="Mask Colors", style="Dark.TLabel").pack(anchor="w", padx=10, pady=5)

def rgb_to_hex(rgb):
    """
    Converts an RGB tuple to a hex string.
    :param rgb: A tuple with three integers (R, G, B), each in the range 0-255.
    :return: A hex string in the format '#RRGGBB'.
    """
    return "#{:02x}{:02x}{:02x}".format(rgb[0], rgb[1], rgb[2])

# Default mask colors, also global variable for mask color customization
mask_colors = {
    "coast_color": rgb_to_hex((174, 235, 52)),
    "inland_color": rgb_to_hex((245, 130, 37)),
    "forest_edge_color": rgb_to_hex((81, 153, 14)),
    "tree_color": rgb_to_hex((66, 191, 50)),
    "water_color": rgb_to_hex((58, 77, 222))
}

def choose_color(color_type: str):
    if color_type not in mask_colors:
        raise ValueError(f"Invalid color type: {color_type}")
    color_code = colorchooser.askcolor(title="Choose a color")
    if color_code[1]:
        mask_colors[color_type] = color_code[1]
        for btn in sidebar_left.winfo_children():
            if isinstance(btn, tk.Button) and btn.winfo_name()== color_type:
                btn["bg"] = color_code[1]
                break
        update_plot()

tk.Button(
    sidebar_left,
    text="Coast Color",
    name="coast_color",
    bg=mask_colors["coast_color"],
    relief="flat",
    foreground=dark_bg,
    command=lambda: choose_color("coast_color")
).pack(anchor="w", padx=10, pady=5)

tk.Button(
    sidebar_left,
    text="Inland Color",
    name="inland_color",
    bg=mask_colors["inland_color"],
    relief="flat",
    foreground=dark_bg,
    command=lambda: choose_color("inland_color")
).pack(anchor="w", padx=10, pady=5)

tk.Button(
    sidebar_left,
    text="Forest Edge Color",
    name="forest_edge_color",
    bg=mask_colors["forest_edge_color"],
    relief="flat",
    foreground=dark_bg,
    command=lambda: choose_color("forest_edge_color")
).pack(anchor="w", padx=10, pady=5)

tk.Button(
    sidebar_left,
    text="Tree Color",
    name="tree_color",
    bg=mask_colors["tree_color"],
    relief="flat",
    foreground=dark_bg,
    command=lambda: choose_color("tree_color")
).pack(anchor="w", padx=10, pady=5)

tk.Button(
    sidebar_left,
    text="Water Color",
    name="water_color",
    bg=mask_colors["water_color"],
    relief="flat",
    foreground=dark_bg,
    command=lambda: choose_color("water_color")
).pack(anchor="w", padx=10, pady=5)

# Splitter
canvas = tk.Canvas(sidebar_left, width=230, height=1, bg="gray", bd=0, highlightthickness=0)
canvas.pack(padx=10, pady=10)

# Title Label
ttk.Label(sidebar_left, text="Building Display", style="Dark.TLabel").pack(anchor="w", padx=10, pady=5)

building_icons = tk.BooleanVar(value=True)

# Checkbutton for toggling building icons
ttk.Checkbutton(sidebar_left, text="Building Icons", variable=building_icons, style="Dark.TCheckbutton", command=update_plot).pack(anchor="w", padx=10, pady=5)

# Splitter
canvas = tk.Canvas(sidebar_left, width=230, height=1, bg="gray", bd=0, highlightthickness=0)
canvas.pack(padx=10, pady=10)

# Title Label
ttk.Label(sidebar_left, text="Path Mask Priority", style="Dark.TLabel").pack(anchor="w", padx=10, pady=5)

# Cost Slider
ttk.Label(sidebar_left, text="Zero Mask:", style="Dark_.TLabel").pack(anchor="w", padx=10, pady=2.5)
cost_1 = tk.DoubleVar(value=1)
cost_1_slider = ttk.Scale(
    sidebar_left, from_=1.0, to=10000.0, orient="horizontal", variable=cost_1,
    style="Horizontal.TScale"
)
cost_1_slider.pack(anchor="w", padx=10, pady=5)

# Cost Slider
ttk.Label(sidebar_left, text="Tree Mask:", style="Dark_.TLabel").pack(anchor="w", padx=10, pady=2.5)
cost_2 = tk.DoubleVar(value=100)
cost_2_slider = ttk.Scale(
    sidebar_left, from_=1.0, to=10000.0, orient="horizontal", variable=cost_2,
    style="Horizontal.TScale"
)
cost_2_slider.pack(anchor="w", padx=10, pady=5)

# Cost Slider
ttk.Label(sidebar_left, text="Water Mask:", style="Dark_.TLabel").pack(anchor="w", padx=10, pady=2.5)
cost_3 = tk.DoubleVar(value=1000)
cost_3_slider = ttk.Scale(
    sidebar_left, from_=1.0, to=10000.0, orient="horizontal", variable=cost_3,
    style="Horizontal.TScale"
)
cost_3_slider.pack(anchor="w", padx=10, pady=5)

# Cost Slider
ttk.Label(sidebar_left, text="Buildings Mask:", style="Dark_.TLabel").pack(anchor="w", padx=10, pady=2.5)
cost_4 = tk.DoubleVar(value=10000)
cost_4_slider = ttk.Scale(
    sidebar_left, from_=1.0, to=10000.0, orient="horizontal", variable=cost_4,
    style="Horizontal.TScale"
)
cost_4_slider.pack(anchor="w", padx=10, pady=5)

# Splitter
canvas = tk.Canvas(sidebar_left, width=230, height=1, bg="gray", bd=0, highlightthickness=0)
canvas.pack(padx=10, pady=10)

style.configure(
    "Dark.TButton",
    background=dark_bg,
    foreground=text_color,
    font=("Arial", 10),
    borderwidth=1,
    focusthickness=0
)

style.map(
    "Dark.TButton",
    background=[("active", highlight_color), ("!active", dark_bg)],
    foreground=[("active", dark_bg), ("!active", text_color)]
)

# Update Button
button = tk.Button(
    sidebar_left, text="Update", 
    background=dark_bg, foreground=text_color,
    font=("Arial", 12, "bold"),
    relief="flat",
    activebackground="#333333",
    activeforeground=text_color,
    highlightbackground="#444444",
    command=load_image
)
button.pack(anchor="w", padx=10, pady=5)

# Load and display the default image
img_path = os.path.join("./mocking_examples", image_listing.get(image_listing.curselection()[0]))  # Select first image
img = cv2.imread(img_path)

# Calculate masks for the first image (predefine globals)
coast_mask, inland_mask, forest_edge_mask, tree_mask, water_mask, buildings, paths_points, bridge_points = mask_deployment(
    get_tree_mask(img_path), get_water_mask(img_path)
)

# Create matplotlib plot
fig = Figure(figsize=(8, 6))
ax = fig.add_subplot(111)

fig.patch.set_facecolor('#2e2e2e')

axes_colors = '#7d7d7d'
ax.spines['bottom'].set_color(axes_colors)
ax.spines['left'].set_color(axes_colors)
ax.spines['top'].set_color(axes_colors)
ax.spines['right'].set_color(axes_colors)
ax.tick_params(colors=axes_colors)
ax.xaxis.label.set_color(axes_colors)
ax.yaxis.label.set_color(axes_colors)
ax.title.set_color(axes_colors)

canvas = FigureCanvasTkAgg(fig, master=root)
canvas_widget = canvas.get_tk_widget()
canvas_widget.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

# Initialize plot
update_plot()

root.mainloop()
