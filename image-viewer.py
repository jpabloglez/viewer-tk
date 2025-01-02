import argparse
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import pydicom
import nibabel as nib
import numpy as np
from PIL import Image, ImageTk
import os
import sys

class MetadataViewer:
    def __init__(self, master, metadata):
        self.master = master
        self.master.title("Metadatos")
        self.master.geometry("600x400")

        # Crear un Treeview
        self.tree = ttk.Treeview(master, columns=("Value"), show="tree headings")
        self.tree.heading("Value", text="Valor")
        self.tree.pack(fill=tk.BOTH, expand=True)

        # Añadir una barra de desplazamiento
        scrollbar = ttk.Scrollbar(master, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Poblar el árbol con los metadatos
        self.populate_tree("", metadata)

    def populate_tree(self, parent, metadata):
        if isinstance(metadata, pydicom.dataset.FileDataset):
            for elem in metadata:
                if elem.VR == "SQ":
                    seq_node = self.tree.insert(parent, "end", text=f"{elem.name} ({elem.tag})", values=("Sequence"))
                    for i, item in enumerate(elem.value):
                        item_node = self.tree.insert(seq_node, "end", text=f"Item {i+1}")
                        self.populate_tree(item_node, item)
                elif elem.VM > 1:
                    values = "\\".join(str(v) for v in elem.value)
                    self.tree.insert(parent, "end", text=f"{elem.name} ({elem.tag})", values=(values))
                else:
                    value = str(elem.value)
                    if len(value) > 50:
                        value = value[:47] + "..."
                    self.tree.insert(parent, "end", text=f"{elem.name} ({elem.tag})", values=(value))
        elif isinstance(metadata, nib.nifti1.Nifti1Image):
            header = metadata.header
            for key, value in header.items():
                if key != 'unused_data':
                    self.tree.insert(parent, "end", text=key, values=(str(value)))

class ImageViewer:
    def __init__(self, master, directory=None, image=None):
        self.master = master
        master.title("Visualizador de Imágenes Médicas")
        
        self.current_slice = 0
        self.image_files = []
        self.image_format = None
        self.current_image = None
        self.image_data = None

        # Frame principal
        self.main_frame = ttk.Frame(master)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Frame para botones
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(pady=10)

        # Botón para cargar directorio
        self.load_button = ttk.Button(self.button_frame, text="Cargar directorio", command=self.load_directory)
        self.load_button.pack(side=tk.LEFT, padx=5)

        # Botón para ver metadatos
        self.metadata_button = ttk.Button(self.button_frame, text="Ver Metadatos", command=self.show_metadata)
        self.metadata_button.pack(side=tk.LEFT, padx=5)

        # Frame para la imagen y los tags
        self.image_tag_frame = ttk.Frame(self.main_frame)
        self.image_tag_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas para mostrar la imagen
        self.canvas = tk.Canvas(self.image_tag_frame)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Frame para los tags básicos
        self.tag_frame = tk.Frame(self.image_tag_frame, bg="#e6f3ff")
        self.tag_frame.pack(fill=tk.X, pady=10)

        # Estilo para las etiquetas
        style = ttk.Style()
        style.configure("Tag.TLabel", background="#e6f3ff")

        # Labels para los tags básicos
        self.tag_labels = [
            ttk.Label(self.tag_frame, text="", style="Tag.TLabel") for _ in range(3)
        ]
        for i, label in enumerate(self.tag_labels):
            label.grid(row=i, column=0, sticky="w", padx=5, pady=2)

        # Slider para navegar entre cortes
        if self.image_format == "DICOM":
            #self.slider = ttk.Scale(self.main_frame, from_=0, to=0, orient=tk.HORIZONTAL, command=self.update_slice_dicom)
            self.slider = tk.Scale(master, from_=0, to=0, orient=tk.HORIZONTAL, command=self.update_slice)

        else:
            self.slider = ttk.Scale(self.main_frame, from_=0, to=0, orient=tk.HORIZONTAL, command=self.update_slice_image)
        self.slider.pack(fill=tk.X, expand=1, pady=10)
        #self.slider.pack(fill=tk.X, expand=1)

        # Bindear las teclas de flecha
        self.master.bind('<Left>', self.previous_slice)
        self.master.bind('<Right>', self.next_slice)

        # Si se proporciona un directorio inicial, cárgalo
        if directory:
            self.load_directory(directory)
        if image:
            self.load_image(image)

        # Labels para los tags DICOM
        self.patient_id_label = ttk.Label(self.tag_frame, text="Patient ID: ", style="Tag.TLabel")
        self.patient_id_label.grid(row=0, column=0, sticky="w", padx=5)
        
        self.patient_age_label = ttk.Label(self.tag_frame, text="Patient Age: ", style="Tag.TLabel")
        self.patient_age_label.grid(row=0, column=1, sticky="w", padx=5)
        
        self.series_modality_label = ttk.Label(self.tag_frame, text="Modality: ", style="Tag.TLabel")
        self.series_modality_label.grid(row=0, column=3, sticky="w", padx=5)

        self.series_desc_label = ttk.Label(self.tag_frame, text="Series Description: ", style="Tag.TLabel")
        self.series_desc_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=5)


    def sort_based_on_instance_number(self):
        """ Sorts the DICOM image files based on the instance number in the DICOM tags. """
        self.image_files.sort(key=lambda x: int(pydicom.dcmread(x).InstanceNumber))

    def load_directory(self, directory=None):
        if directory is None:
            directory = filedialog.askdirectory()
        if directory:
            self.image_files = [os.path.join(directory, f) for f in os.listdir(directory) 
                                if f.endswith(('', '.dcm'))]
            
            if len(self.image_files) == 0:
                messagebox.showinfo("Información", "No se encontraron archivos DICOM o NIfTI en el directorio seleccionado.")
            else:
                self.sort_based_on_instance_number()
                self.image_format = "DICOM"
    
        elif self.image_files:
            self.load_image(self.image_files[0])
            self.image_format = "NIfTI"
        else:
            messagebox.showinfo("Información", "No se encontraron archivos DICOM o NIfTI en el directorio seleccionado.")

    def load_image(self, file_path):
        """
        Load an image file and update the slider and current slice.

        Parameters:
            file_path (str): The path to the image file.
        """
        if file_path.endswith(('.nii', '.nii.gz')):
            self.current_image = nib.load(file_path)
            self.image_data = self.current_image.get_fdata()
            self.slider.config(to=self.image_data.shape[-1] - 1)
            self.update_slice_image(0)
        else:
            self.current_image = pydicom.dcmread(file_path)
            self.image_data = self.current_image.pixel_array
            self.slider.config(to=0)
            self.update_slice_dicom(0)

    def update_slice_dicom(self, value):
        """
        Update the displayed image to the specified slice.

        Parameters:
            value (float): The slice number to display.
        """
        self.current_slice = int(float(value))
        if self.image_files:
            # Read the DICOM file corresponding to the current slice
            dicom_file = self.image_files[self.current_slice]
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

    def update_slice_image(self, value):
        self.current_slice = int(float(value))
        if self.image_data is not None:
            if len(self.image_data.shape) == 3:
                img = self.image_data[:, :, self.current_slice]
            elif len(self.image_data.shape) == 2:
                img = self.image_data
            else:
                messagebox.showerror("Error", "Formato de imagen no soportado")
                return

            img = (img - np.min(img)) / (np.max(img) - np.min(img)) * 255
            img = Image.fromarray(img.astype('uint8'))

            # Redimensionar la imagen para que ocupe todo el ancho de la ventana
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

            self.canvas.delete("all")
            self.canvas.create_image(window_width//2, window_height//2, anchor=tk.CENTER, image=img)
            self.canvas.image = img

            # Actualizar los tags básicos
            self.update_tags()

            # Actualizar el valor del slider
            self.slider.set(self.current_slice)

    def update_tags(self):
        if isinstance(self.current_image, pydicom.dataset.FileDataset):
            self.tag_labels[0].config(text=f"Patient ID: {self.current_image.get('PatientID', 'N/A')}")
            self.tag_labels[1].config(text=f"Patient Age: {self.current_image.get('PatientAge', 'N/A')}")
            self.tag_labels[2].config(text=f"Series Description: {self.current_image.get('SeriesDescription', 'N/A')}")
        elif isinstance(self.current_image, nib.nifti1.Nifti1Image):
            header = self.current_image.header
            self.tag_labels[0].config(text=f"Dimensions: {header['dim'][1:4]}")
            self.tag_labels[1].config(text=f"Voxel size: {header['pixdim'][1:4]}")
            self.tag_labels[2].config(text=f"Data type: {header.get_data_dtype()}")

    def on_resize(self, event):
        if self.image_format == "DICOM":
            self.update_slice_dicom(self.current_slice)
        else:
            self.update_slice_image(self.current_slice)

    def show_metadata(self):
        if self.current_image:
            metadata_window = tk.Toplevel(self.master)
            MetadataViewer(metadata_window, self.current_image)
        else:
            messagebox.showinfo("Información", "Por favor, cargue una imagen primero.")

    def previous_slice(self, event):
        if self.current_slice > 0:
            self.current_slice -= 1
            if self.image_format == "DICOM":
                self.update_slice_dicom(self.current_slice)
            else:
                self.update_slice_image(self.current_slice)

    def next_slice(self, event):
        if self.current_slice < self.slider.cget("to"):
            self.current_slice += 1
            if self.image_format == "DICOM":
                self.update_slice_dicom(self.current_slice)
            else:
                self.update_slice_image(self.current_slice)

def main(directory=None, image=None):
    root = tk.Tk()
    root.geometry("800x600")  # Tamaño inicial de la ventana
    viewer = ImageViewer(root, directory, image)
    root.bind("<Configure>", viewer.on_resize)  # Vincular el evento de redimensionamiento
    root.mainloop()

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
    main(args.directory, args.image)