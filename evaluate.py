"""
Idea of this script:

1. Load Model -> model
2. Val Normal data
3. Val Abnormal data
4. Take random subset of normal and abnormal data + their labels and mix them (of course keep labels in right order)
5. Feed each image through model
6. Take pixel wise difference between original image and reconstruction
7. Then y_true and y_score are known -> plot ROC Curve
8. ROC curve gives a good threshold
9. Show the reconstructed images and how they have been classified
"""

import argparse

import yaml
from sklearn.metrics import roc_curve, auc

from models import *

parser = argparse.ArgumentParser(description='Generic runner for VAE models')
parser.add_argument('--config', '-c',
                    dest="filename",
                    metavar='FILE',
                    help='path to the config file',
                    default='configs/vae.yaml')
parser.add_argument('--load', '-l',
                    dest='checkpoint_file',
                    metavar='FILE',
                    help='Path to checkpoint to load experiment from')
parser.add_argument('--save_plots',
                    type=str,
                    help="Specify a suffix which is used to save the plots to roc_curve_suffix.svg and reconstructed "
                         "classified_suffix.svg")

args = parser.parse_args()

with open(args.filename, 'r') as file:
    try:
        config = yaml.safe_load(file)
    except yaml.YAMLError as exc:
        print(exc)

filename_roc_curve = None
filename_reconstructed_classified = None

if args.save_plots:
    filename_roc_curve = "roc_curve_" + args.save_plots + ".pdf"
    filename_reconstructed_classified = "reconstructed_classified_" + args.save_plots + ".pdf"

model = vae_models[config['model_params']['name']](config['exp_params'], **config['model_params'])
model = model.load_from_checkpoint(args.checkpoint_file)
model.eval()

transform = model.data_transforms()

dataset_normal = ConcreteCracksDataset(root_dir=config['exp_params']['data_path'],
                                       split="val",
                                       abnormal_data=False,
                                       transform=transform)

dataset_abnormal = ConcreteCracksDataset(root_dir=config['exp_params']['data_path'],
                                         split="val",
                                         abnormal_data=True,
                                         transform=transform)

dataloader_normal = DataLoader(dataset_normal,
                               batch_size=150,
                               shuffle=True,
                               drop_last=True)

dataloader_abnormal = DataLoader(dataset_abnormal,
                                 batch_size=150,
                                 shuffle=True,
                                 drop_last=True)

all_labels = []
all_pixel_wise_difference_means = []

single_batch_for_visualization_labels = None
single_batch_for_visualization_predictions = None
single_batch_for_visualization_pixel_wise_difference = None
single_batch_for_visualization_pixel_wise_difference_mean = None

for i, (normal_data, abnormal_data) in enumerate(zip(dataloader_normal, dataloader_abnormal)):
    batch_normal, labels_normal = normal_data
    batch_abnormal, labels_abnormal = abnormal_data

    batch = torch.cat([batch_normal, batch_abnormal], dim=0)
    labels = torch.cat([labels_normal, labels_abnormal], dim=0)

    with torch.no_grad():
        predictions = model.generate(batch)

    pixel_wise_diff_mean = torch.mean(torch.abs(predictions - batch), dim=(1, 2, 3)).numpy()

    all_labels = np.concatenate([all_labels, labels])
    all_pixel_wise_difference_means = np.concatenate([all_pixel_wise_difference_means, pixel_wise_diff_mean], axis=0)

    if i == 0:
        single_batch_for_visualization_labels = labels
        single_batch_for_visualization_predictions = predictions
        single_batch_for_visualization_pixel_wise_difference = torch.abs(predictions - batch)
        single_batch_for_visualization_pixel_wise_difference_mean = pixel_wise_diff_mean
    print("Iteration {} done".format(i))

fpr, tpr, thresholds = roc_curve(all_labels, all_pixel_wise_difference_means)
roc_auc = auc(fpr, tpr)

best_threshold = thresholds[np.argmax(tpr - fpr)]

lw = 2
plt.plot(fpr, tpr, color='darkorange',
         lw=lw, label='ROC curve (area = %0.2f)' % roc_auc)
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
plt.title('Receiver operating characteristic')
plt.legend(loc="lower right")

if filename_roc_curve is not None:
    plt.savefig(filename_roc_curve)

print("Best Threshold: {}".format(best_threshold))

single_batch_for_visualization_labels_predicted = single_batch_for_visualization_pixel_wise_difference_mean > best_threshold
fig, (ax1, ax2, ax3, ax4) = plt.subplots(nrows=4, ncols=1)

ax1.imshow(
    vutils.make_grid(single_batch_for_visualization_predictions[single_batch_for_visualization_labels_predicted == 0],
                     normalize=True, nrow=5).permute(2, 1, 0).numpy())
ax1.set_title("Reconstructed - Predicted Negative")

ax2.imshow(
    vutils.make_grid(single_batch_for_visualization_pixel_wise_difference[single_batch_for_visualization_labels_predicted == 0],
                     normalize=True, nrow=5).permute(2, 1, 0).numpy())
ax2.set_title("Pixelwise difference - Predicted Negative")

ax3.imshow(
    vutils.make_grid(single_batch_for_visualization_predictions[single_batch_for_visualization_labels_predicted == 1],
                     normalize=True, nrow=5).permute(2, 1, 0).numpy())
ax3.set_title("Reconstructed - Predicted Positive")

ax4.imshow(
    vutils.make_grid(single_batch_for_visualization_pixel_wise_difference[single_batch_for_visualization_labels_predicted == 1],
                     normalize=True, nrow=5).permute(2, 1, 0).numpy())
ax4.set_title("Pixelwise difference - Predicted Positive")

plt.tight_layout()

if filename_reconstructed_classified is not None:
    plt.savefig(filename_reconstructed_classified)

plt.show()
print("Done")
