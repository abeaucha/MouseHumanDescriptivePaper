# ----------------------------------------------------------------------------
# train_multilayer_perceptron.py 
# Author: Antoine Beauchamp
# Created: December 15th, 2020

"""
Train a multi-layer perceptron

Description
-----------
This script trains a multi-layer perceptron neural network to classify mouse
voxels into a specified number of neuroanatomical atlas regions. 

Once the network is trained, the final layer is removed to obtain the
transformation from the input space to the latent space defined by the last
hidden layer. 

The modified network architecture is used to transform aggregated regional
mouse and human gene expression matrices from the input space into the latent
space. An option also exists to transform voxel- and sample-wise expression
matrices as well.
"""

# Packages -------------------------------------------------------------------

import pandas                 as pd
import numpy                  as np
import random
import argparse
import os
from datatable                import fread

import torch
import torch.nn.functional    as F
from torch                    import nn
from torch.optim              import SGD, AdamW
from torch.optim.lr_scheduler import OneCycleLR
from torch.cuda               import is_available

from skorch                   import NeuralNetClassifier
from skorch.callbacks         import LRScheduler
from skorch.helper            import DataFrameTransformer

from sklearn.metrics          import accuracy_score, confusion_matrix

from captum.attr              import IntegratedGradients

# Functions ------------------------------------------------------------------

def parse_args():
    
    parser = argparse.ArgumentParser(
        formatter_class = argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument(
        "--datadir",
        type = str,
        default = 'data/',
        help = "Directory containing input data."
    )
    
    parser.add_argument(
        "--outdir",
        type = str,
        default = 'data/MLP_outcomes/',
        help = "Directory in which to write neural net outcomes."
    )
    
    parser.add_argument(
        "--labels",
        type = str,
        default = 'region5',
        choices = ['region5', 
                   'region11',
                   'region28',
                   'region46',
                   'region67',
                   'region134'],
        help = "Class of mouse labels on which to train."
    )
    
    parser.add_argument(
        "--mousedata",
        type = str,
        default = 'region134',
        choices = ['region5', 
                   'region11',
                   'region28',
                   'region46',
                   'region67',
                   'region134'],
        help = "Mouse data to apply the trained network to."
    )
    
    parser.add_argument(
        "--humandata",
        type = str,
        default = 'region166',
        choices = ['region5',
                   'region16',
                   'region56',
                   'region79',
                   'region88',
                   'region166'],
        help = "Human data to apply the trained network to."
    )
    
    parser.add_argument(
        "--nunits",
        type = int,
        default = 500,
        help = "Number of hidden units in the network."
    )
    
    parser.add_argument(
        "--L2",
        type = float,
        default = 1e-6,
        help = "Weight decay"
    )
    
    parser.add_argument(
        "--nepochs",
        type = int,
        default = 200,
        help = "Number of epochs to train over."
    )
    
    parser.add_argument(
        "--learningrate",
        type = float,
        default = 1e-5,
        help = "Learning rate during training."
    )
    
    parser.add_argument(
        '--totalsteps',
        type = int,
        help = "Number of steps to use in optimizer."
    )
    
    parser.add_argument(
        '--optimizer',
        type = str,
        default = 'SGD'
    )
    
    parser.add_argument(
        "--confusionmatrix",
        type = str,
        default = 'false',
        choices = ['true', 'false'],
        help = ("Option to compute confusion matrix from training set "
                "predictions.")
    )
    
    parser.add_argument(
        "--voxeltransform",
        type = str,
        default = 'true',
        choices = ['true', 'false'],
        help = ("Option to transform the voxel-wise data using the "
                "modified MLP.")
    )
    
    parser.add_argument(
        '--integratedgrads',
        type = str,
        default = 'false',
        choices = ['true', 'false'],
        help = ("Option to compute integrated gradients for "
               "feature attributions.")
    )
    
    parser.add_argument(
        '--seed',
        type = int,
        help = ("Random seed")
    )
    
    args = vars(parser.parse_args())
    
    return args
    
    
# Main ------------------------------------------------------------------------

def main():

    #Load command line arguments
    args = parse_args()
    
    datadir = args['datadir']
    outdir = args['outdir']
    
    datadir = os.path.join(datadir, '')
    outdir = os.path.join(outdir, '')
    
    if os.path.exists(outdir) == False:
        print('Output directory {} not found. Creating it...'.format(outdir))
        os.makedirs(outdir)
    
    # Import data -------------------------------------------------------------

    #Set up files for import
    #Mouse voxelwise data to train over
    file_voxel = ("MouseExpressionMatrix_"
                  "voxel_coronal_maskcoronal_"
                  "log2_grouped_imputed_labelled_scaled.csv")
    filepath_voxel = os.path.join(datadir, file_voxel)
    
    #Mouse and human data to pass to network
    file_mouse = ("MouseExpressionMatrix_ROI_{}_scaled.csv"
                  .format(args['mousedata'].capitalize()))
    file_human = ("HumanExpressionMatrix_ROI_{}_scaled.csv"
                  .format(args['humandata'].capitalize()))
    filepath_mouse = os.path.join(datadir, file_mouse)
    filepath_human = os.path.join(datadir, file_human)

    print("Importing data...")

    #Import data
    dfExprVoxel = (fread(filepath_voxel, header = True)
                   .to_pandas())
    dfExprMouse = (fread(filepath_mouse, header = True)
                   .to_pandas())
    dfExprHuman = (fread(filepath_human, header = True)
                   .to_pandas())
    
    # Process data ------------------------------------------------------------

    print("Preparing data for learning...")

    #Identify which columns contain labels
    indLabels = dfExprVoxel.columns.str.match('Region')

    #Extract matrix of gene expression values
    dfInput = dfExprVoxel.loc[:,~indLabels]
    
    dfInput = dfInput.loc[:, dfInput.columns.isin(dfExprHuman.columns)]
    
    dfInputMouse = dfExprMouse.loc[:, dfExprMouse.columns.isin(dfInput.columns)]
    dfInputHuman = dfExprHuman.loc[:, dfExprHuman.columns.isin(dfInput.columns)]
    
    labelcol = args['labels'].capitalize()
    
    print("Using labels: {}".format(labelcol))
    
    #Create a new data frame containing intermediate labels
    dfLabels = dfExprVoxel[[labelcol]].copy()

    #Convert labels to category type
    dfLabels.loc[:,labelcol] = dfLabels.loc[:,labelcol].astype('category')

    # Create an instance of the transformer
    dftx = DataFrameTransformer()

    # Fit and transform the input and label data frames
    X_temp = dftx.fit_transform(dfInput)
    y_temp = dftx.fit_transform(dfLabels)

    # Extract the arrays from the dictionaries.
    X = X_temp['X']
    y = y_temp[labelcol]

    # Initialize the network --------------------------------------------------

    print("Initializing neural network...")
    
    seed = args['seed']
    if seed is not None:
        np.random.seed(seed)
        torch.manual_seed(seed)
        random.seed(seed)
    
    #Get network parameters from command line args
    hidden_units = args['nunits']
    weight_decay = args['L2']
    max_epochs = args['nepochs']
    total_steps = args['totalsteps']
    learning_rate = args['learningrate']
    optimizer = args['optimizer']
    
    if total_steps is None:
        total_steps = max_epochs
        
    if optimizer == 'AdamW':
        optimizer = AdamW
    elif optimizer == 'SGD':
        optimizer = SGD
    else:
        raise ValueError
    
    if is_available() == True:
        print("GPU available. Training network using GPU...")
        device = 'cuda'
    else:
        print("GPU unavailable. Training network using CPU...")
        device = 'cpu'

    #Define network architecture
    class ClassifierModule(nn.Module):
        
        def __init__(
            self,
            input_units,
            output_units,
            hidden_units,
            apply_output_layer = True #Flag to apply output layer
        ):
            super(ClassifierModule, self).__init__()

            self.apply_output_layer = apply_output_layer

            self.hidden1 = nn.Linear(input_units, hidden_units)
            self.hidden2 = nn.Linear(hidden_units, hidden_units)
            self.hidden3 = nn.Linear(hidden_units, hidden_units)
            self.output = nn.Linear(hidden_units, output_units)

        def forward(self, X, **kwargs):
            X = F.relu(self.hidden1(X))
            X = F.relu(self.hidden2(X))
            X = F.relu(self.hidden3(X))

            #If flag is True, apply output layer
            if self.apply_output_layer is True:
                X = F.softmax(self.output(X), dim = -1)

            return X
        
    net_module = ClassifierModule(input_units = X.shape[1],
                                  output_units = len(np.unique(y)),
                                  hidden_units = hidden_units)

    #Create the classifier
    net = NeuralNetClassifier(net_module,
                              train_split = None,
                              optimizer = optimizer,
                              optimizer__weight_decay = weight_decay,
                              max_epochs = max_epochs,
                              callbacks = [('lr_scheduler',
                                            LRScheduler(policy=OneCycleLR,
                                                        total_steps=total_steps,
                                                        cycle_momentum=False,  
                                                        max_lr=learning_rate))],
                              device = device)

    
    # Train the network ------------------------------------------------------
    
    #Fit the network
    net.fit(X, y)
    
    #Predict training labels
    y_pred = net.predict(X)
    
    #Compute training accuracy
    print("Training accuracy: {}".format(accuracy_score(y, y_pred)))

    #Match the dummy variable labels to the region names
    dfLabels['y'] = y
    dfLabelsUnique = dfLabels.sort_values('y').drop_duplicates()
    
    
    # Compute training confusion matrix --------------------------------------
    
    #Switch to compute confusion matrix
    if args['confusionmatrix'] == 'true':
    
        print("Computing confusion matrix from training set...")
    
        #Compute confusion matrix and store as data frame
        dfConfusionMat = pd.DataFrame(confusion_matrix(y, y_pred))
    
        #Assign region names to the confusion matrix columns
        dfConfusionMat.columns = dfLabelsUnique[labelcol].astype('str')
    
        #Assign region names to the confusion matrix rows
        dfConfusionMat['TrueLabels'] = (dfLabelsUnique[labelcol]
                                        .astype('str')
                                        .reset_index(drop = True))
        
        #File to save confusion matrix
        fileConfMat = "MLP_ConfusionMatrix_Training"+\
        "_"+args['labels'].capitalize()+\
        "_Layers3"+\
        "_Units"+str(args['nunits'])+\
        "_L2"+str(args['L2'])+".csv"
    
        #Write confusion matrix to file
        dfConfusionMat.to_csv(os.path.join(outdir, fileConfMat),
                              index = False)
        
        
    # Feature importance -----------------------------------------------------
    
    if args['integratedgrads'] == 'true':
    
        #Structures to examine
        target_structs = ['Caudoputamen',
                          'Primary motor area',
                          'Infralimbic area']
    
        #List of genes
        genes = dfInput.columns.to_numpy()
    
        #Convert X to tensor
        X_tensor = torch.from_numpy(X).type(torch.FloatTensor)
        X_tensor.requires_grad_()    
    
        #Set up integrated gradients
        ig = IntegratedGradients(net_module)

        #Iterate over structs
        integrated_grads = np.zeros((len(target_structs), len(genes)))
        for i, struct in enumerate(target_structs):
        
            print("Computing integrated gradients for region: {}".format(struct))
    
            #Grab label from structure name
            target_label = int(dfLabelsUnique
                              .loc[dfLabelsUnique[labelcol] == struct, ['y']]
                              .values[0][0])
        
            #Compute gradients
            attr = ig.attribute(X_tensor, 
                                target = target_label,
                                internal_batch_size = X_tensor.shape[0])

            #Average over data points
            attr_mean = np.mean(attr.detach().numpy(), axis = 0)
        
            #Assign to array
            integrated_grads[i,:] = attr_mean
    
        #Convert to data frame
        integrated_grads = pd.DataFrame(integrated_grads, columns = genes)
        integrated_grads['Region'] = target_structs
    
        #Output filename
        file_integrated_grads = ('MLP_{}_Layers3_Units{}_L2{}_IntegratedGradients.csv'
                                 .format(args['labels'].capitalize(),
                                         args['nunits'], 
                                         args['L2']))
    
        file_integrated_grads = os.path.join(outdir, file_integrated_grads)
    
        #Write to file
        integrated_grads.to_csv(file_integrated_grads, index = False)
    
    
    # Predict label probabilities for mouse/human data -----------------------
        
    print("Applying trained network to mouse and human data...")

    #Put mouse/human data into appropriate format for network        
    X_Mouse = dftx.fit_transform(dfInputMouse)['X']
    X_Human = dftx.fit_transform(dfInputHuman)['X']
    
    #Compute label probabilities for mouse/human data
    dfPredictionsMouse = pd.DataFrame(net.predict_proba(X_Mouse))
    dfPredictionsHuman = pd.DataFrame(net.predict_proba(X_Human))
    
    #Include label names as columns
    dfPredictionsMouse.columns = dfLabelsUnique[labelcol].astype('str')
    dfPredictionsHuman.columns = dfLabelsUnique[labelcol].astype('str')
    
    #Include true labels
    dfPredictionsMouse['TrueLabel'] = dfExprMouse['Region']
    dfPredictionsHuman['TrueLabel'] = dfExprHuman['Region']
    
    #File to save mouse probabilities
    fileMouseProb = "MLP_"+args['labels'].capitalize()+\
    "_Layers3"+\
    "_Units"+str(args['nunits'])+\
    "_L2"+str(args['L2'])+\
    "_MouseProb_"+args['mousedata'].capitalize()+'.csv'
    
    #File to save human probabilities
    fileHumanProb = "MLP_"+args['labels'].capitalize()+\
    "_Layers3"+\
    "_Units"+str(args['nunits'])+\
    "_L2"+str(args['L2'])+\
    "_HumanProb_"+args['humandata'].capitalize()+'.csv'
    
    #Write probability data to file
    dfPredictionsMouse.to_csv(os.path.join(outdir, fileMouseProb),
                              index = False)
    dfPredictionsHuman.to_csv(os.path.join(outdir, fileHumanProb),
                              index = False)
    
    # Extract hidden layer for mouse/human data ------------------------------

    #Change the mode of the network to extract a hidden layer
    net.module_.apply_output_layer = False
    
    #Apply the modified network to the mouse and human data to get the
    #hidden units
    dfMouseTransformed = pd.DataFrame(net.predict_proba(X_Mouse))
    dfHumanTransformed = pd.DataFrame(net.predict_proba(X_Human))
    
    #Include region information
    dfMouseTransformed['Region'] = dfExprMouse['Region']
    dfHumanTransformed['Region'] = dfExprHuman['Region']

    #File to save transformed mouse data
    fileMouseTx = "MLP_"+args['labels'].capitalize()+\
    "_Layers3"+\
    "_Units"+str(args['nunits'])+\
    "_L2"+str(args['L2'])+\
    "_MouseTx_"+args['mousedata'].capitalize()+'.csv'
    
    #File to save transformed human data
    fileHumanTx = "MLP_"+args['labels'].capitalize()+\
    "_Layers3"+\
    "_Units"+str(args['nunits'])+\
    "_L2"+str(args['L2'])+\
    "_HumanTx_"+args['humandata'].capitalize()+'.csv'
    
    #Save new mouse and human data to file
    dfMouseTransformed.to_csv(os.path.join(outdir,fileMouseTx), index = False)
    dfHumanTransformed.to_csv(os.path.join(outdir,fileHumanTx), index = False)
    
    
    if args['voxeltransform'] == 'true':
        
        dfMouseVoxelTransformed = pd.DataFrame(net.predict_proba(X))
        dfMouseVoxelTransformed['Region'] = dfLabels[labelcol]
        
        file_voxel_human = ("HumanExpressionMatrix_"
                            "samples_pipeline_abagen_labelled_scaled.csv")
        filepath_voxel_human = os.path.join(datadir, file_voxel_human)
        
        dfExprVoxelHuman = (fread(filepath_voxel_human, header = True)
                            .to_pandas())
        indLabelsHuman = dfExprVoxelHuman.columns.str.match('Region')
        dfInputVoxelHuman = dfExprVoxelHuman.loc[:, ~indLabels]
        X_VoxelHuman = dftx.fit_transform(dfInputVoxelHuman)['X']
        dfHumanVoxelTransformed = pd.DataFrame(net.predict_proba(X_VoxelHuman))
        dfHumanVoxelTransformed['Region'] = dfExprVoxelHuman[args['humandata'].capitalize()]
        
        fileMouseVoxelTx = "MLP_"+args['labels'].capitalize()+\
        "_Layers3"+\
        "_Units"+str(args['nunits'])+\
        "_L2"+str(args['L2'])+\
        "_MouseVoxelTx.csv"
        
        fileHumanVoxelTx = "MLP_"+args['labels'].capitalize()+\
        "_Layers3"+\
        "_Units"+str(args['nunits'])+\
        "_L2"+str(args['L2'])+\
        "_HumanVoxelTx.csv"

        dfMouseVoxelTransformed.to_csv(os.path.join(outdir,fileMouseVoxelTx),
                                       index = False)
        dfHumanVoxelTransformed.to_csv(os.path.join(outdir,fileHumanVoxelTx),
                                       index = False)
        
if __name__ == "__main__":
    main()
