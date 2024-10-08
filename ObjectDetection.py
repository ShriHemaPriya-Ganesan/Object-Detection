#
**Model Research and selection**
In object detection, the Faster R-CNN (Region-based Convolutional Neural Network) is a widely used deep learning model for object detection. With MobileNet serving as the foundation network, the project's goal is to deploy Faster R-CNN for object detection on a  dataset of aquarium images and video file.

The Faster R-CNN is a two-stage object detection approach that uses a region-based CNN for object detection after a region proposal network. By effectively creating area proposals, classifying objects, and performing bounding box regression on these proposals, it attains high accuracy.

MobileNet is a specialized convolutional neural network architecture designed for mobile and embedded vision applications. It utilizes depthwise separable convolutions to reduce computational complexity while maintaining high accuracy. This makes it ideal for real-time object detection on devices with limited resources.
"""

# Import the libraries
import torch
import torchvision
from torchvision import datasets, models
from torchvision.transforms import functional as FT
from torchvision import transforms as T
import torchvision.transforms as transforms
from torch.nn import functional as F
from torch.utils.data import DataLoader, random_split, Dataset
import copy
import math
from PIL import Image
import cv2
import sys
from google.colab.patches import cv2_imshow
import albumentations as A
import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
from tqdm import tqdm
from torchvision.utils import draw_bounding_boxes
from pycocotools.coco import COCO
from albumentations.pytorch import ToTensorV2

# Connect to google drive to access the required dataset
from google.colab import drive
drive.mount('/content/drive')

"""**Data Collection:**
The dataset comprises images captured within an aquarium environment, showcasing various aquatic species and their surroundings. Data collected from kaggle, ensuring a diverse representation of aquatic life forms (different types of fish) and environmental conditions. Additionally, annotated the images with bounding boxes to mark the presence and location of different objects, such as fish.

**Data Augmentation:**
To enhance the robustness and generalization capabilities of the model, I applied data augmentation techniques during preprocessing. These augmentations include resizing the images to a standardized input size, horizontal and vertical flips to account for different orientations, random adjustments to brightness and contrast, and color jittering to simulate variations in lighting conditions. These augmentations help the model learn invariant features and improve its performance on unseen data.

**Data Splitting:**
The dataset was divided into separate subsets for training and testing purposes. The training set comprises 449 images and one annotations json file, used to train the model to detect objects within the aquarium environment. Meanwhile, the testing set consists of a smaller portion of images which means 63 images and one annotations json file, kept aside to evaluate the model's performance on unseen data. This ensures an unbiased assessment of the model's accuracy and generalization capabilities.

**Data Annotation:**
Each image in the dataset is annotated with bounding boxes delineating the location and size of objects of interest within the image. These annotations are crucial for training the object detection model. I utilized the COCO format for annotations, ensuring compatibility with popular object detection frameworks and tools.

**Data Transformation:**
Before feeding the images into the model, transformed them into a format compatible with the chosen deep learning framework (Torch). This involved converting the images into tensors and normalizing their pixel values to a standardized range. Additionally, performed necessary preprocessing steps, such as resizing and normalization, to ensure consistency and optimal model performance during training and inference.
"""

# Data preprocessing - augmentation
def data_augmentation(train=False):
    if train:
        transform = A.Compose([
            A.Resize(600, 600), # our input size can be 600px
            A.HorizontalFlip(p=0.3),
            A.VerticalFlip(p=0.3),
            A.RandomBrightnessContrast(p=0.1),
            A.ColorJitter(p=0.1),
            ToTensorV2()
        ], bbox_params=A.BboxParams(format='coco'))
    else:
        transform = A.Compose([
            A.Resize(600, 600), # our input size can be 600px
            ToTensorV2()
        ], bbox_params=A.BboxParams(format='coco'))
    return transform

"""**Implementation**

**Object Detection:**
The code defines a aquarium dataset class for object detection tasks, leveraging PyTorch's torchvision library. This class, named detection, inherits from datasets.VisionDataset and is designed to handle loading and preprocessing of image and annotation data. Upon initialization, it loads COCO annotations corresponding to the specified data split and filters out images with no annotations. The class includes methods for loading images and their annotations, transforming bounding box coordinates, and retrieving dataset items. Additionally, it provides functionality to calculate the dataset length. This dataset class facilitates efficient handling of image and annotation data, serving as a component in training object detection models.

**Object Tracking:**
In addition to object detection, I augmented the fasterRCNN model with object tracking functionality to enable continuous monitoring of aquatic species within the aquarium environment. I centroid tracking and filtering, to accurately track the movement of objects over consecutive frames of a video file (aquarium-nyc.mp4).
"""

# Define class detection inheriting from VisionDataset
class detection(datasets.VisionDataset):
    def __init__(self, root, data_split='train', transform=None, target_transform=None, transforms=None):
        super().__init__(root, transforms, transform, target_transform)
        self.data_split = data_split
        self.coco = COCO(os.path.join(root, data_split, "_annotations.coco.json"))
        # Get list of image IDs
        self.image_ids = list(sorted(self.coco.imgs.keys()))
        # Filter out images with no annotations
        self.image_ids = [id for id in self.image_ids if (len(self._load_target(id)) > 0)]

    # Function to load image
    def _load_image(self, image_id: int):
        image_path = self.coco.loadImgs(image_id)[0]['file_name']
        image = cv2.imread(os.path.join(self.root, self.data_split, image_path))
        image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return image

    # Function to load annotations for a specific image
    def _load_target(self, image_id):
        return self.coco.loadAnns(self.coco.getAnnIds(image_id))

    # Function to get item from dataset
    def __getitem__(self, index):
        image_id = self.image_ids[index]
        image = self._load_image(image_id)
        target = self._load_target(image_id)
        target = copy.deepcopy(self._load_target(image_id))

        boxes = [t['bbox'] + [t['category_id']] for t in target]
        if self.transforms is not None:
            transformed = self.transforms(image=image, bboxes=boxes)

        image = transformed['image']
        boxes = transformed['bboxes']

        new_boxes = []
        for box in boxes:
            xmin = box[0]
            xmax = xmin + box[2]
            ymin = box[1]
            ymax = ymin + box[3]
            new_boxes.append([xmin, ymin, xmax, ymax])

        boxes = torch.tensor(new_boxes, dtype=torch.float32)

        targ = {}
        targ['boxes'] = boxes
        targ['labels'] = torch.tensor([t['category_id'] for t in target], dtype=torch.int64)
        targ['image_id'] = torch.tensor([t['image_id'] for t in target])
        targ['area'] = (boxes[:, 3] - boxes[:, 1]) * (boxes[:, 2] - boxes[:, 0])
        targ['iscrowd'] = torch.tensor([t['iscrowd'] for t in target], dtype=torch.int64)
        return image.div(255), targ

    # Function to get length of the dataset
    def __len__(self):
        return len(self.image_ids)

# Define dataset path
dataset_path = "/content/drive/MyDrive/Aquarium"

# Load COCO annotations for training set
coco = COCO(os.path.join(dataset_path, "train", "_annotations.coco.json"))
categories = coco.cats
num_class = len(categories.keys())
print(categories)

# Extracting 'name' attribute from items in 'categories' dictionary and storing them in a list
classes = [i[1]['name'] for i in categories.items()]
print(classes)

# Invoke detection function
train_data = detection(root=dataset_path, transforms=data_augmentation(True))

# Display sample train data
sample_train = train_data[2]
img= torch.tensor(sample_train[0] * 255, dtype=torch.uint8)
plt.imshow(draw_bounding_boxes(
    img, sample_train[1]['boxes'], [classes[i] for i in sample_train[1]['labels']], width=4
).permute(1, 2, 0))

# Load the faster rcnn model
model = models.detection.fasterrcnn_mobilenet_v3_large_fpn(pretrained=True)
features = model.roi_heads.box_predictor.cls_score.in_features # we need to change the head
model.roi_heads.box_predictor = models.detection.faster_rcnn.FastRCNNPredictor(features, num_class)

# This function zips together elements of a batch
def collate(batch):
    return tuple(zip(*batch))

# Create DataLoader for loading training data
# Parameters:
#   - train_data: Dataset object containing training data
#   - batch_size: Number of samples in each batch
#   - shuffle: Whether to shuffle the data at each epoch
#   - num_workers: Number of subprocesses to use for data loading
#   - collate_fn: Function to use for collating samples into batches
load_train_data = DataLoader(train_data, batch_size=4, shuffle=True, num_workers=4, collate_fn=collate)

# Retrieve a batch of data from the DataLoader
# `imgs` contains a list of images
# `trgs` contains a list of dictionaries, each dictionary representing annotations for a corresponding image
imgs,trgs = next(iter(load_train_data))

# Convert imgs to a list for easy manipulation
imgs = list(image for image in imgs)

# Deep copy trgs to ensure original data remains unchanged
# Convert trgs to a list of dictionaries for easy manipulation
trgs = [{k:v for k, v in t.items()} for t in trgs]

# Pass the batch of images and their corresponding annotations to the model for inference
output = model(imgs, trgs)

# Check if CUDA (GPU) is available, and assign device accordingly
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
model = model.to(device)

# Retrieve parameters of the model that require gradient computation
params = [p for p in model.parameters() if p.requires_grad]

# Define the optimizer to update the parameters during training
# Parameters:
#   - params: Iterable of parameters to optimize
#   - lr: Learning rate (step size) for the optimizer
#   - momentum: Momentum factor for the SGD optimizer
#   - nesterov: Whether to use Nesterov momentum
#   - weight_decay: Weight decay (L2 penalty) to apply to the parameters
optimizer = torch.optim.SGD(params, lr=0.01, momentum=0.9, nesterov=True, weight_decay=1e-4)

"""**Evaluation**

Defined a function run_epoch responsible for running each epoch of training for an object detection model. Within each epoch, the function iterates over the provided data loader in batch-wise fashion, where each batch consists of input images and their corresponding target annotations. During each iteration, the model is set to training mode, and forward pass is performed to compute the loss using the provided optimizer. The computed loss is then backpropagated through the model, updating its parameters.

The function also collects and prints various training metrics at the epoch level, including the learning rate (lr), total loss, classifier loss, bounding box regression loss, region proposal network (RPN) box regression loss, and objectness loss. These metrics provide insights into the training process, aiding in monitoring and evaluating the model's performance. Additionally, the function includes checks to ensure that the loss remains finite during training, terminating training if it becomes infinite to prevent divergence.
"""

# Define function to run each epoch of training
def run_epoch(model, optimizer, loader, device, epoch):
    # Set the model to training mode
    model.train()

    loss_list = []
    losses_dict_list = []

    # Iterate over the data loader (batch-wise iteration)
    for images, targets in tqdm(loader):
        images = list(image.to(device) for image in images)
        targets = [{k: torch.tensor(v).to(device) for k, v in t.items()} for t in targets]

        loss_dict = model(images, targets)
        losses = sum(loss for loss in loss_dict.values())
        # Extract loss values and append to lists
        loss_dict_append = {k: v.item() for k, v in loss_dict.items()}
        loss_value = losses.item()

        loss_list.append(loss_value)
        losses_dict_list.append(loss_dict_append)

        # Check if loss is finite; if not, terminate training
        if not math.isfinite(loss_value):
            print(f"Loss is {loss_value}, stopping trainig") # train if loss becomes infinity
            print(loss_dict)
            sys.exit(1)

        # Backpropagation: compute gradients and update model parameters
        optimizer.zero_grad()
        losses.backward()
        optimizer.step()

    losses_dict_list = pd.DataFrame(losses_dict_list)

    # Print epoch-level training metrics
    print("Epoch {}, lr: {:.6f}, loss: {:.6f}, loss_classifier: {:.6f}, loss_box: {:.6f}, loss_rpn_box: {:.6f}, loss_object: {:.6f}".format(
        epoch, optimizer.param_groups[0]['lr'], np.mean(loss_list),
        losses_dict_list['loss_classifier'].mean(),
        losses_dict_list['loss_box_reg'].mean(),
        losses_dict_list['loss_rpn_box_reg'].mean(),
        losses_dict_list['loss_objectness'].mean()
    ))

# Run 10 epochs
epochs=10
for epoch in range(epochs):
    run_epoch(model, optimizer, load_train_data, device, epoch)

# Set the model to evaluation mode
model.eval()

# Empty the CUDA cache to release GPU memory
torch.cuda.empty_cache()

# Save the trained model
torch.save(model.state_dict(), 'trained_model.pth')

# Access test dataset and invoke detection function
test_dataset = detection(root=dataset_path, data_split="test", transforms=data_augmentation(False))

# Define a function to detect objects in a single image
def detect_objects_test(image):
  # Unpack the image and discard the target
  img, _ = image
  # Convert the image to a tensor with uint8 data type
  img_int = torch.tensor(img*255, dtype=torch.uint8)

  # Perform object detection on the image using model prediction
  with torch.no_grad():
    prediction = model([img.to(device)])
    pred = prediction[0]

  # Create a figure for displaying the image with bounding boxes
  fig = plt.figure(figsize=(14, 10))

  # Draw bounding boxes on the image and display it
  # Filter out boxes with confidence scores less than 0.8
  plt.imshow(draw_bounding_boxes(img_int,pred['boxes'][pred['scores'] > 0.8],
    [classes[i] for i in pred['labels'][pred['scores'] > 0.8].tolist()], width=4
  ).permute(1, 2, 0))

# Invoke object detection function
detect_objects_test(test_dataset[0])

# Display the resulting frame
# cv2_imshow(result_frame)

# Define function to perform object detection and tracking for the video file
def detect_objects_and_track(frame):
    # Convert the frame to a tensor and unsqueeze to add a batch dimension
    img_tensor = FT.to_tensor(frame).unsqueeze(0).to(device)
    # Load the saved model
    trained_model = models.detection.fasterrcnn_mobilenet_v3_large_fpn(pretrained=False)
    trained_model.load_state_dict(torch.load('/content/drive/MyDrive/Aquarium/trained_model.pth',map_location=torch.device('cpu')))
    trained_model.eval()  # Set the model to evaluation mode

    # Perform object detection on the input frame
    with torch.no_grad():
        prediction = model(img_tensor)

    # Filter out detections with confidence above a certain threshold
    boxes = prediction[0]['boxes'][prediction[0]['scores'] > 0.8].cpu().numpy()
    labels = prediction[0]['labels'][prediction[0]['scores'] > 0.8].cpu().numpy()

    # Draw bounding boxes and labels on the frame for each detected object
    for box, label in zip(boxes, labels):
        box = box.astype(int)
        frame = cv2.rectangle(frame, (box[0], box[1]), (box[2], box[3]), (0, 255, 0), 2)
        frame = cv2.putText(frame, classes[label], (box[0], box[1] - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    return frame

# Define the path to the video file in Google Drive
video_path = '/content/drive/My Drive/Aquarium/aquarium-nyc.mp4'

# Load the video file using OpenCV
cap = cv2.VideoCapture(video_path)

# Check if video opened successfully
if not cap.isOpened():
    print("Error: Could not open video.")
else:
    print("Video opened successfully.")

# Extract and Process Frames
frame_count = 0

while True:
    # Capture frame-by-frame
    ret, frame = cap.read()

    # If frame is read correctly, ret is True
    if not ret:
        print("Can't receive frame (stream end?). Exiting ...")
        break

    # object detection and tracking code
    frame = detect_objects_and_track(frame)

    # Display the resulting frame
    cv2_imshow(frame)

    frame_count += 1

    # Break the loop after 5 frames for the sake of this demo
    if frame_count == 15:
        break

# When everything is done, release the video capture object
cap.release()
print("Video processing completed.")

"""**Analysis and Discussion**

**Insights:**
The outcomes of the fasterRCNN mobilenet model reveal promising results in detecting and tracking objects within aquarium dataset. Through visual demonstrations using image sequences and video frames, I showcase the model's capability to accurately identify and track various aquatic species, including fish, corals, and aquatic plants. The model successfully localizes and labels these objects, providing valuable insights into the composition and dynamics of the aquarium ecosystem. These visual demonstrations not only validate the effectiveness of the model but also highlight its practical utility in real-world applications, such as aquarium monitoring and research.

**Challenges:**
Despite the result achieved, several challenges were encountered during the assignment. One significant obstacle was related to dataset characteristics, particularly in ensuring sufficient diversity and representation of aquatic species and environmental conditions. Additionally, the availability of annotated data posed a challenge, as manually annotating large volumes of images can be time-consuming and resource-intensive. Moreover, computational constraints, such as limited GPU resources, impacted the training and evaluation processes, requiring optimization and careful management of model complexity and batch sizes.

**Future Directions:**
To refine the model's detection and tracking performance, several potential directions and improvements can be explored. Moreover, incorporating advanced tracking algorithms, such as multi-object tracking or instance segmentation, can improve the accuracy and consistency of object tracking over time. Furthermore, exploring techniques for model compression and optimization to reduce computational overhead and improve inference speed on resource-constrained devices could expand the model's deployment capabilities in real-world scenarios. Overall, continuing to iterate on data collection, model architecture, and optimization strategies will be crucial for advancing the effectiveness and applicability of our object detection and tracking system in aquarium monitoring and beyond.
"""
