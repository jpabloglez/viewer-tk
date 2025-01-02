import sys
import shutil
import tkinter as tk
import argparse
import tempfile
from tkinter import filedialog, ttk
import nibabel as nib
import pydicom
import numpy as np
from PIL import Image, ImageTk
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider

import os

class DICOMViewer:
    def __init__(self, master):
        self.master = master
        master.title("Visualizador DICOM")

        self.current_slice = 0
        self.current_ds = None # Current DICOM dataset

        self.dicom_files = []

        # Frame principal
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame para botones
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(pady=10)

        # Botón para cargar directorio
        self.load_button = tk.Button(master, text="Cargar directorio DICOM", command=self.load_directory)
        self.load_button.pack()

        # Botón para ver metadatos
        self.metadata_button = ttk.Button(self.button_frame, text="Ver Metadatos DICOM", command=self.show_metadata)
        self.metadata_button.pack(side=tk.LEFT, padx=5)

        # Frame para la imagen y los tags
        self.image_tag_frame = ttk.Frame(self.main_frame)
        self.image_tag_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas para mostrar la imagen
        #self.canvas = tk.Canvas(master, width=512, height=512)
        #self.canvas.pack()
        # Canvas para mostrar la imagen (ahora ocupa todo el ancho)
        self.canvas = tk.Canvas(self.image_tag_frame)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Frame para los tags DICOM
        #self.tag_frame = ttk.Frame(self.image_tag_frame)
        self.tag_frame = tk.Frame(self.image_tag_frame, bg="#e6f3ff")  # Azul claro
        self.tag_frame.pack(fill=tk.X, pady=10)

        # Estilo para las etiquetas
        style = ttk.Style()
        style.configure("Tag.TLabel", background="#e6f3ff")

        # Labels para los tags DICOM
        self.patient_id_label = ttk.Label(self.tag_frame, text="Patient ID: ", style="Tag.TLabel")
        self.patient_id_label.grid(row=0, column=0, sticky="w", padx=5)
        
        self.patient_age_label = ttk.Label(self.tag_frame, text="Patient Age: ", style="Tag.TLabel")
        self.patient_age_label.grid(row=0, column=1, sticky="w", padx=5)
        
        self.series_modality_label = ttk.Label(self.tag_frame, text="Modality: ", style="Tag.TLabel")
        self.series_modality_label.grid(row=0, column=3, sticky="w", padx=5)

        self.series_desc_label = ttk.Label(self.tag_frame, text="Series Description: ", style="Tag.TLabel")
        self.series_desc_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5)

        # Slider para navegar entre cortes
        self.slider = tk.Scale(master, from_=0, to=0, orient=tk.HORIZONTAL, command=self.update_slice)
        self.slider.pack(fill=tk.X, expand=1)

        # Bind slider to keyboard events
        self.master.bind('<Left>', self.previous_slice)
        self.master.bind('<Right>', self.next_slice)
    
    def sort_based_on_instance_number(self):
        """ Sorts the DICOM image files based on the instance number in the DICOM tags. """
        self.dicom_files.sort(key=lambda x: int(pydicom.dcmread(x).InstanceNumber))
        
    def load_directory(self, directory=None):
        """
        Load a directory of DICOM files and update the slider and current slice.
        """
        if directory is None:
            # Ask the user to select a directory
            directory = filedialog.askdirectory()


        # If a directory is selected
        if directory:
            # Get a list of DICOM files in the directory
            dicom_files = [
                os.path.join(directory, f)
                for f in os.listdir(directory)
                #if f.endswith('.dcm')
            ]
            if len(dicom_files) == 0:
                print("No DICOM files found in the selected directory.")
                return
            
            self.dicom_files = dicom_files

            # Sort the list of DICOM files
            self.sort_based_on_instance_number()

            # Update the slider max value
            self.slider.config(to=len(self.dicom_files) - 1)

            # Update the current slice to the first slice
            #m_slice = int(len(self.dicom_files) / 2)
            self.update_slice(0)

    def update_slice_basic(self, value):
        self.current_slice = int(value)
        if self.dicom_files:
            dicom_file = self.dicom_files[self.current_slice]
            ds = pydicom.dcmread(dicom_file)
            img = ds.pixel_array

            if 'RescaleSlope' in ds and 'RescaleIntercept' in ds:
                img = img * ds.RescaleSlope + ds.RescaleIntercept

            img = (img - np.min(img)) / (np.max(img) - np.min(img)) * 255
            img = Image.fromarray(img.astype('uint8'))
            img = ImageTk.PhotoImage(img)

            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
            self.canvas.image = img

    def update_slice(self, value):
        """
        Update the displayed image to the specified slice.

        Parameters:
            value (float): The slice number to display.
        """
        self.current_slice = int(float(value))
        if self.dicom_files:
            # Read the DICOM file corresponding to the current slice
            dicom_file = self.dicom_files[self.current_slice]
            ds = pydicom.dcmread(dicom_file)
            self.current_ds = ds

            img = ds.pixel_array

            # Rescale the image if necessary
            if 'RescaleSlope' in ds and 'RescaleIntercept' in ds:
                img = img * ds.RescaleSlope + ds.RescaleIntercept

            # Normalize the image to the range [0, 255]
            img = (img - np.min(img)) / (np.max(img) - np.min(img)) * 255
            img = Image.fromarray(img.astype('uint8'))

            # Resize the image to fit the window
            window_width = self.canvas.winfo_width()
            window_height = self.canvas.winfo_height()
            aspect_ratio = img.width / img.height
            new_width = window_width
            new_height = int(new_width / aspect_ratio)
            
            if new_height > window_height:
                new_height = window_height
                new_width = int(new_height * aspect_ratio)

            img = img.resize((new_width, new_height), Image.LANCZOS)
            img = ImageTk.PhotoImage(img)

            # Update the displayed image
            self.canvas.delete("all")
            self.canvas.create_image(window_width//2, window_height//2, anchor=tk.CENTER, image=img)
            self.canvas.image = img

            # Update the DICOM tags
            self.patient_id_label.config(text=f"Patient ID: {ds.get('PatientID', 'N/A')}")
            self.patient_age_label.config(text=f"Patient Age: {ds.get('PatientAge', 'N/A')}")
            #self.patient_sex_label.config(text=f"Patient Sex: {ds.get('PatientSex', 'N/A')}")
            self.series_modality_label.config(text=f"Series Modality: {ds.get('Modality', 'N/A')}")
            self.series_desc_label.config(text=f"Series Description: {ds.get('SeriesDescription', 'N/A')}")

            # Update the slider
            self.slider.set(self.current_slice)

    def on_resize(self, event):
        """
        Call update_slice when the window is resized.

        This function is called whenever the window is resized. It calls the
        update_slice method to update the displayed image accordingly.

        Parameters:
            event (Event): The event that triggered the function.

        Returns:
            None
        """
        # Call update_slice to update the displayed image
        # when the window is resized
        self.update_slice(self.current_slice)

    def show_metadata(self):
        if self.current_ds:
            metadata_window = tk.Toplevel(self.master)
            DICOMMetadataViewer(metadata_window, self.current_ds)
        else:
            tk.messagebox.showinfo("Información", "Por favor, cargue un estudio DICOM primero.")

    def previous_slice(self, event):
        """
        Decrement the current slice and update the displayed image.

        This function is called when the user clicks the "Previous" button.
        It decrements the current slice index and calls the update_slice method
        to update the displayed image.

        Parameters:
            event (Event): The event that triggered the function.

        Returns:
            None
        """
        # Check if there is a previous slice
        if self.current_slice > 0:
            # Decrement the current slice index
            self.current_slice -= 1
            # Call update_slice to update the displayed image
            self.update_slice(self.current_slice)

    def next_slice(self, event):
        """
        Increment the current slice and update the displayed image.

        This function is called when the user clicks the "Next" button.
        It increments the current slice index and calls the update_slice method
        to update the displayed image.

        Parameters:
            event (Event): The event that triggered the function.

        Returns:
            None
        """
        # Check if there is a next slice
        if self.current_slice < len(self.dicom_files) - 1:
            # Increment the current slice index
            self.current_slice += 1
            # Call update_slice to update the displayed image
            self.update_slice(self.current_slice)

class DICOMMetadataViewer:
    def __init__(self, master, dicom_dataset):
        self.master = master
        self.master.title("Metadatos DICOM")
        self.master.geometry("600x400")

        # Crear un Treeview
        self.tree = ttk.Treeview(master, columns=("Value", "VR"), show="tree headings")
        self.tree.heading("Value", text="Valor")
        self.tree.heading("VR", text="VR")
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Añadir una barra de desplazamiento
        scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Poblar el árbol con los metadatos DICOM
        self.populate_tree("", dicom_dataset)

    def populate_tree(self, parent, dataset):
        for elem in dataset:
            if elem.VR == "SQ":
                # Para secuencias, crear un subárbol
                seq_node = self.tree.insert(parent, "end", text=f"{elem.name} ({elem.tag})", values=("Sequence", elem.VR))
                for i, item in enumerate(elem.value):
                    item_node = self.tree.insert(seq_node, "end", text=f"Item {i+1}")
                    self.populate_tree(item_node, item)
            elif elem.VM > 1:
                # Para elementos con múltiples valores
                values = "\\".join(str(v) for v in elem.value)
                self.tree.insert(parent, "end", text=f"{elem.name} ({elem.tag})", values=(values, elem.VR))
            else:
                # Para elementos simples
                value = str(elem.value)
                if len(value) > 50:  # Truncar valores muy largos
                    value = value[:47] + "..."
                self.tree.insert(parent, "end", text=f"{elem.name} ({elem.tag})", values=(value, elem.VR))

class NiftiViewerMpl:
    def __init__(self, file_path):
        self.file_path = file_path
        self.nifti_img = nib.load(file_path)
        self.data = self.nifti_img.get_fdata()
        print("Min:", np.min(self.data), "Max:", np.max(self.data)) 
        self.shape = self.data.shape
        self.num_slices = self.shape[2]  # Use all slices in z-direction
        
        self.temp_dir = tempfile.mkdtemp()
        
        self.fig, self.ax = plt.subplots(figsize=(10, 10))
        plt.subplots_adjust(bottom=0.25)
        
        self.slider_ax = plt.axes([0.2, 0.1, 0.6, 0.03])
        self.slider = Slider(self.slider_ax, 'Slice', 0, self.num_slices - 1, valinit=0, valstep=1)        
        self.slider.on_changed(self.update)
        
        self.img = self.ax.imshow(self.get_slice(self.num_slices - 1), cmap='gray')
        self.ax.set_title(f'Slice 1/{self.num_slices}')
        
        self.fig.canvas.mpl_connect('close_event', self.on_close)

    def get_slice(self, index):
        slice_data = self.data[:, :, index]
        return slice_data
        return self.normalize_slice(slice_data)

    def normalize_slice(self, slice_data):
        slice_min = np.min(slice_data)
        slice_max = np.max(slice_data)
        if slice_min == slice_max:
            return np.zeros_like(slice_data)  # Return a black image if the slice is uniform
        return (slice_data - slice_min) / (slice_max - slice_min)


    def update(self, val):
        index = int(self.slider.val)
        slice_data = self.get_slice(index)
        print(f"Updating slice {index + 1}/{self.num_slices}")
        print(f"Slice data shape: {slice_data.shape}")
        print(f"Slice data min: {np.min(slice_data)}, max: {np.max(slice_data)}")
        self.img.set_data(slice_data)
        self.ax.set_title(f'Slice {index + 1}/{self.num_slices}')
        self.fig.canvas.draw_idle()

    def on_close(self, event):
        shutil.rmtree(self.temp_dir)

    def show_image(self):
        plt.show()

class NiftiImage:
    def __init__(self, file_path):
        self.file_path = file_path
        self.nifti_img = nib.load(file_path)
        self.data = self.nifti_img.get_fdata()
        self.shape = self.data.shape
        self.num_slices = self.shape[2]
        self.temp_dir = tempfile.mkdtemp()
        self.render_slices()

    def render_slices(self):
        for i in range(self.num_slices):
            slice_data = self.data[:, :, i]
            normalized_slice = self.normalize_slice(slice_data)
            img = Image.fromarray((normalized_slice * 255).astype(np.uint8))
            img.save(os.path.join(self.temp_dir, f'slice_{i:03d}.png'))

    def normalize_slice(self, slice_data):
        slice_min = np.min(slice_data)
        slice_max = np.max(slice_data)
        if slice_min == slice_max:
            return np.zeros_like(slice_data)
        return (slice_data - slice_min) / (slice_max - slice_min)

    def get_slice_path(self, index):
        return os.path.join(self.temp_dir, f'slice_{index:03d}.png')

    def cleanup(self):
        shutil.rmtree(self.temp_dir)

class NiftiViewer(tk.Tk):
    def __init__(self, nifti_image):
        super().__init__()
        self.nifti_image = nifti_image
        self.title("NIFTI Viewer")
        self.geometry("800x600")

        self.current_slice = 0
        self.photo = None  # Store the PhotoImage object

        self.create_widgets()
        self.update_image()

    def create_widgets(self):
        self.image_label = ttk.Label(self)
        self.image_label.pack(expand=True, fill=tk.BOTH)

        self.slider = ttk.Scale(
            self, 
            from_=0, 
            to=self.nifti_image.num_slices - 1, 
            orient=tk.HORIZONTAL, 
            command=self.on_slider_change
        )
        self.slider.pack(fill=tk.X, padx=20, pady=10)

        self.slice_label = ttk.Label(self, text=f"Slice: 1/{self.nifti_image.num_slices}")
        self.slice_label.pack(pady=5)

    def on_slider_change(self, value):
        self.current_slice = int(float(value))
        self.update_image()

    def update_image(self):
        image_path = self.nifti_image.get_slice_path(self.current_slice)
        image = Image.open(image_path)
        
        # Resize image to fit the window
        window_width = self.winfo_width()
        window_height = self.winfo_height() - 100  # Subtracting space for slider and label
        image.thumbnail((window_width, window_height), Image.Resampling.LANCZOS)
        
        self.photo = ImageTk.PhotoImage(image)
        self.image_label.config(image=self.photo)
        self.slice_label.config(text=f"Slice: {self.current_slice + 1}/{self.nifti_image.num_slices}")

    def on_closing(self):
        self.nifti_image.cleanup()
        self.destroy()

    def on_resize(self, event):
        # Update image size when window is resized
        self.update_image()

def render_dicom(directory):
    root = tk.Tk()
    root.geometry("800x600")  # Tamaño inicial de la ventana
    viewer = DICOMViewer(root)
    viewer.load_directory(directory)
    root.bind("<Configure>", viewer.on_resize)  # Vincular el evento de redimensionamiento
    root.mainloop()

def render_nifti(file_path):
    root = tk.Tk()
    root.geometry("800x600")  # Tamaño inicial de la ventana
    nifti_image = NiftiImage(file_path)
    viewer = NiftiViewer(nifti_image)
    #viewer.show_image()
    viewer.protocol("WM_DELETE_WINDOW", viewer.on_closing)
    viewer.bind("<Configure>", viewer.on_resize)

    viewer.mainloop()

def main(args):
    """ Main function """
    if args.directory:
        render_dicom(args.directory)
    else:
        render_nifti(args.image)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualizador de imágenes médicas DICOM y NIfTI")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-d', '--directory', metavar='DIR', type=str, help='Directorio de DICOM')
    group.add_argument('-i', '--image', metavar='IMAGE', type=str, help='Imagen NIfTI')
    args = parser.parse_args()
    
    if args.directory:
        if not os.path.isdir(args.directory):
            print(f"Error: El directorio '{args.directory}' no existe.")
            sys.exit(1)
    elif args.image:
        if not os.path.isfile(args.image):
            print(f"Error: El archivo '{args.image}' no existe.")
            sys.exit(1)
    
    main(args)