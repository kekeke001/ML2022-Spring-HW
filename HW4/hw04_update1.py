# -*- coding: utf-8 -*-
"""hw04_(1).ipynb

Automatically generated by Colab.

Original file is located at
    https://colab.research.google.com/drive/1l61kKpsNEalLUQGR4qyzhNOB5iIB2oPk

# Task description
- Classify the speakers of given features.
- Main goal: Learn how to use transformer.
- Baselines:
  - Easy: Run sample code and know how to use transformer.
  - Medium: Know how to adjust parameters of transformer.
  - Strong: Construct [conformer](https://arxiv.org/abs/2005.08100) which is a variety of transformer.
  - Boss: Implement [Self-Attention Pooling](https://arxiv.org/pdf/2008.01077v1.pdf) & [Additive Margin Softmax](https://arxiv.org/pdf/1801.05599.pdf) to further boost the performance.

- Other links
  - Kaggle: [link](https://www.kaggle.com/t/ac77388c90204a4c8daebeddd40ff916)
  - Slide: [link](https://docs.google.com/presentation/d/1HLAj7UUIjZOycDe7DaVLSwJfXVd3bXPOyzSb6Zk3hYU/edit?usp=sharing)
  - Data: [link](https://drive.google.com/drive/folders/1vI1kuLB-q1VilIftiwnPOCAeOOFfBZge?usp=sharing)

# Download dataset
- Data is [here](https://drive.google.com/drive/folders/1vI1kuLB-q1VilIftiwnPOCAeOOFfBZge?usp=sharing)
"""

# !wget https://github.com/MachineLearningHW/ML_HW4_Dataset/releases/latest/download/Dataset.tar.gz.partaa
# !wget https://github.com/MachineLearningHW/ML_HW4_Dataset/releases/latest/download/Dataset.tar.gz.partab
# !wget https://github.com/MachineLearningHW/ML_HW4_Dataset/releases/latest/download/Dataset.tar.gz.partac
# !wget https://github.com/MachineLearningHW/ML_HW4_Dataset/releases/latest/download/Dataset.tar.gz.partad

# !cat Dataset.tar.gz.part* > Dataset.tar.gz

# # unzip the file
# !tar zxvf Dataset.tar.gz

from google.colab import drive
drive.mount('/content/drive')
# 原链接丢失，故将数据传到自己的google drive 上
!cp '/content/drive/MyDrive/Dataset.tar.gz' '/content/'
# unzip the file
!tar zxvf Dataset.tar.gz

"""## Fix Random Seed"""

import numpy as np
import torch
import random

def set_seed(seed):
    np.random.seed(seed)
    random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

set_seed(87)

"""# Data

## Dataset
- Original dataset is [Voxceleb2](https://www.robots.ox.ac.uk/~vgg/data/voxceleb/vox2.html).
- The [license](https://creativecommons.org/licenses/by/4.0/) and [complete version](https://www.robots.ox.ac.uk/~vgg/data/voxceleb/files/license.txt) of Voxceleb2.
- We randomly select 600 speakers from Voxceleb2.
- Then preprocess the raw waveforms into mel-spectrograms.

- Args:
  - data_dir: The path to the data directory.
  - metadata_path: The path to the metadata.
  - segment_len: The length of audio segment for training.
- The architecture of data directory \\
  - data directory \\
  |---- metadata.json \\
  |---- testdata.json \\
  |---- mapping.json \\
  |---- uttr-{random string}.pt \\

- The information in metadata
  - "n_mels": The dimention of mel-spectrogram.
  - "speakers": A dictionary.
    - Key: speaker ids.
    - value: "feature_path" and "mel_len"


For efficiency, we segment the mel-spectrograms into segments in the traing step.
"""

import os
import json
import torch
import random
from pathlib import Path
from torch.utils.data import Dataset
from torch.nn.utils.rnn import pad_sequence


class myDataset(Dataset):
	def __init__(self, data_dir, segment_len=128):
		self.data_dir = data_dir
		self.segment_len = segment_len

		# mapping文件的处理--> speakerid：分类
		mapping_path = Path(data_dir) / "mapping.json"
		# json文件的加载
		mapping = json.load(mapping_path.open())
		self.speaker2id = mapping["speaker2id"] #self.speaker2id: {'id00464': 0, 'id00559': 1, 'id00578': 2, 'id00905': 3,...

		# Load metadata of training data.
		metadata_path = Path(data_dir) / "metadata.json"
		metadata = json.load(open(metadata_path))["speakers"] # {'id1':[],'id2':[]...}

		# Get the total number of speaker.
		self.speaker_num = len(metadata.keys())
		self.data = []
		for speakerid in metadata.keys():
			for utterances in metadata[speakerid]:
               #  metadata[speakerid]格式：
               #  [{'feature_path': 'uttr-18e375195dc146fd8d14b8a322c29b90.pt', 'mel_len': 435}
               #  {'feature_path': 'uttr-da9917d5853049178487c065c9e8b718.pt', 'mel_len': 490}...]
				self.data.append([utterances["feature_path"], self.speaker2id[speakerid]])
				# data 通过speakerid，将*.pt数据与其分类对应起来 data:(num_*.pt,2)
        #self.data:[['uttr-18e375195dc146fd8d14b8a322c29b90.pt', 436],
        #           ['uttr-da9917d5853049178487c065c9e8b718.pt', 436],...]
        #一共600个speaker,436表示第436个speaker

	def __len__(self):
			return len(self.data)

	# Dataloader会自动调用数据集类的__getitem__()方法
	# __ getitem __() 的作用是让类拥有迭代功能，只要类中有 __ getitem __() 方法，这个类的对象就是迭代器
	def __getitem__(self, index):
		feat_path, speakerid = self.data[index]
		# Load preprocessed mel-spectrogram.
		# mel就是.pt文件
		mel = torch.load(os.path.join(self.data_dir, feat_path))
    # mel.size():torch.Size([len(mel), 40])
		#将mel切片成固定长度 --保证输入长度相同
		if len(mel) > self.segment_len:
			#随机选取切片起始点
			start = random.randint(0, len(mel) - self.segment_len)
			# Get a segment with "segment_len" frames.
			mel = torch.FloatTensor(mel[start:start+self.segment_len])
		else:
			#为什么小于segment_len不填充？  填充在dataloader中完成
			mel = torch.FloatTensor(mel)
		# 将speakerid转换成张量
		speaker = torch.FloatTensor([speakerid]).long()
		return mel, speaker

	def get_speaker_number(self):
		return self.speaker_num # 600

"""## Dataloader
- Split dataset into training dataset(90%) and validation dataset(10%).
- Create dataloader to iterate the data.
"""

import torch
from torch.utils.data import DataLoader, random_split
from torch.nn.utils.rnn import pad_sequence


def collate_batch(batch): #用于整理数据的函数，参数为dataloader中的一个batch
	# Process features within a batch.
	"""Collate a batch of data."""
	# data:[['uttr-18e375195dc146fd8d14b8a322c29b90.pt', 436],
        # ['uttr-da9917d5853049178487c065c9e8b718.pt', 436],...]
	mel, speaker = zip(*batch)
  # mel ('uttr-18e375195dc146fd8d14b8a322c29b90.pt','uttr-da9917d5853049178487c065c9e8b718.pt',..)
	# speaker (436,436,..)
	# mel中元素长度不相同时，将所有的mel元素填充到最长的元素的长度，填充的值由padding_value决定
	# batch_first=True 表示返回的填充后的张量中，批次维度（batch dimension）将排在第一维
	mel = pad_sequence(mel, batch_first=True, padding_value=-20)    # pad log 10^(-20) which is very small value.
	# mel: (batch size, length, 40)
	return mel, torch.FloatTensor(speaker).long()


def get_dataloader(data_dir, batch_size, n_workers):
	"""Generate dataloader"""
	# dataset是类实例化的对象
	dataset = myDataset(data_dir)
	speaker_num = dataset.get_speaker_number()
	# 分离测试集核验证集
	trainlen = int(0.9 * len(dataset))
	lengths = [trainlen, len(dataset) - trainlen]
	trainset, validset = random_split(dataset, lengths)


	# 调用 DataLoader 对象的 __iter__() 方法时，它会遍历数据集，并对每个样本依次调用数据集类的 __getitem__() 方法
	# DataLoader 将这些数据组成一个 batch，并返回给模型进行训练或推理。
	train_loader = DataLoader(
		# trainset: 是一个数据集对象，即 myDataset 类的实例。这个数据集对象包含了训练数据的全部信息，包括数据存储路径、样本数量等
		trainset,
		batch_size=batch_size,
		shuffle=True,
		# drop_last=True: 这表示当数据样本数不能被 batch_size 整除时，丢弃最后一个不完整的 batch。
		# 将其设置为 True 可以避免最后一个 batch 的样本数不足以构成一个完整的 batch，从而导致训练过程中出现错误。
		drop_last=True,
		# n_workers 参数用于指定在数据加载过程中使用的工作进程的数量
		num_workers=n_workers,
		pin_memory=True,
		# 在加载数据时，DataLoader 会调用 collate_fn 函数对一个 batch 中的样本进行批处理前的预处理操作
		collate_fn=collate_batch,
	)
	valid_loader = DataLoader(
		validset,
		batch_size=batch_size,
		num_workers=n_workers,
		drop_last=True,
		pin_memory=True,
		collate_fn=collate_batch,
	)

	return train_loader, valid_loader, speaker_num

"""# Model
- TransformerEncoderLayer:
  - Base transformer encoder layer in [Attention Is All You Need](https://arxiv.org/abs/1706.03762)
  - Parameters:
    - d_model: the number of expected features of the input (required).

    - nhead: the number of heads of the multiheadattention models (required).

    - dim_feedforward: the dimension of the feedforward network model (default=2048).

    - dropout: the dropout value (default=0.1).

    - activation: the activation function of intermediate layer, relu or gelu (default=relu).

- TransformerEncoder:
  - TransformerEncoder is a stack of N transformer encoder layers
  - Parameters:
    - encoder_layer: an instance of the TransformerEncoderLayer() class (required).

    - num_layers: the number of sub-encoder-layers in the encoder (required).

    - norm: the layer normalization component (optional).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class Classifier(nn.Module):
	def __init__(self, d_model=80, n_spks=600, dropout=0.1):
		super().__init__()
		# Project the dimension of features from that of input into d_model.
		# 将输入的语音特征的维度从 40 维投影到一个更高维度的空间 d_model；这个投影操作可以帮助模型更好地理解输入特征。
		self.prenet = nn.Linear(40, d_model)
		# TODO:
		#   Change Transformer to Conformer.
		#   https://arxiv.org/abs/2005.08100
		# d_model：编码器中特征的维度。
		# dim_feedforward：编码器层中全连接层的隐藏单元数。
		# nhead：多头自注意力机制中注意力头的数量
		# encoder_layer代表encoder的一个层
		self.encoder_layer = nn.TransformerEncoderLayer(
			d_model=d_model, dim_feedforward=256, nhead=2
		)
		# num_layers 代表encoder_layer个数，一般transformer的encoder是多个encoder_layer叠加
		self.encoder = nn.TransformerEncoder(self.encoder_layer, num_layers=4)

		# Project the the dimension of features from d_model into speaker nums.
		self.pred_layer = nn.Sequential(
			nn.Linear(d_model, d_model),
			nn.ReLU(),
			nn.Linear(d_model, n_spks),
		)

	def forward(self, mels):
		"""
		args:
			mels: (batch size, length, 40)
		return:
			out: (batch size, n_spks)
		"""
		# 特征处理部分
		# out: (batch size, length, d_model)
		out = self.prenet(mels)
		# out: (length, batch size, d_model)
		out = out.permute(1, 0, 2)
		# The encoder layer expect features in the shape of (length, batch size, d_model).
		# 通常情况下，Transformer 编码器层的输出格式为 (length, batch size, d_model)--进行特征张量的转置操作，以适应 Transformer 编码器层的输入格式要求。
		# 将特征张量送入 Transformer 编码器层进行编码。Transformer 编码器层可以帮助模型在特征序列中捕获全局的上下文信息，并生成具有丰富语义的特征表示。
		out = self.encoder(out)
		# out: (batch size, length, d_model)
		# transpose 也可以对三维进行维度变换啊
		out = out.transpose(0, 1)
		# mean pooling,dim=1上求平均 -- 个人理解是对每个语音特征进行降维处理
		# 均值操作可能有助于聚焦于整个语音片段的总体特征，而不仅仅是每个帧的局部特征。
		# stats: (batch size, d_model)
		# .pt:(时间窗口数,特征维度)
		stats = out.mean(dim=1)

		# 分类预测部分
		# out: (batch, n_spks)
		out = self.pred_layer(stats)
		return out

"""# Learning rate schedule
- For transformer architecture, the design of learning rate schedule is different from that of CNN.
- Previous works show that the warmup of learning rate is useful for training models with transformer architectures.
- The warmup schedule
  - Set learning rate to 0 in the beginning.
  - The learning rate increases linearly from 0 to initial learning rate during warmup period.
"""

import math

import torch
from torch.optim import Optimizer
from torch.optim.lr_scheduler import LambdaLR

# 动态调整学习率的过程
def get_cosine_schedule_with_warmup(
	optimizer: Optimizer,
	# 预热阶段（Warmup：在训练开始时，学习率会从 0 线性增加到初始设定的最大学习率。预热阶段的步数由参数 num_warmup_steps 指定。
	num_warmup_steps: int,
	# 余弦退火阶段（Cosine Annealing）：预热阶段之后，学习率会根据余弦函数的形状逐渐减小。
	# 余弦退火阶段的总步数由参数 num_training_steps 指定，而余弦函数的周期数由参数 num_cycles 控制。
	num_training_steps: int,
	# 余弦函数的周期数为 0.5，也就是说一个完整的周期只需要总训练步数的一半
	# 在这个周期内，学习率会从最大值逐渐减小到零，然后重新开始。
	# 这样的设置可以使得学习率在前半段训练过程中变化平滑，并且在后半段训练过程中重新开始。
	num_cycles: float = 0.5,
	last_epoch: int = -1,
):
	"""
	Create a schedule with a learning rate that decreases following the values of the cosine function between the
	initial lr set in the optimizer to 0, after a warmup period during which it increases linearly between 0 and the
	initial lr set in the optimizer.

	Args:
		optimizer (:class:`~torch.optim.Optimizer`):The optimizer for which to schedule the learning rate.
		num_warmup_steps (:obj:`int`):The number of steps for the warmup phase.
		num_training_steps (:obj:`int`):The total number of training steps.
		num_cycles (:obj:`float`, `optional`, defaults to 0.5):
		The number of waves in the cosine schedule (the defaults is to just decrease from the max value to 0
		following a half-cosine).
		last_epoch (:obj:`int`, `optional`, defaults to -1):The index of the last epoch when resuming training.

	Return:
		:obj:`torch.optim.lr_scheduler.LambdaLR` with the appropriate schedule.
	"""
	def lr_lambda(current_step):
		# Warmup -- 预热阶段，呈线性增长
		if current_step < num_warmup_steps:
			return float(current_step) / float(max(1, num_warmup_steps))
		# decadence
		progress = float(current_step - num_warmup_steps) / float(
			max(1, num_training_steps - num_warmup_steps)
		)
		return max(
			0.0, 0.5 * (1.0 + math.cos(math.pi * float(num_cycles) * 2.0 * progress))
		)
	# 表示上一个 epoch 的索引，默认为 -1。如果提供了该参数，调度器将从上一个 epoch 结束的地方继续调度学习率
	return LambdaLR(optimizer, lr_lambda, last_epoch)

"""# Model Function
- Model forward function.
"""

import torch


def model_fn(batch, model, criterion, device):
	"""Forward a batch through the model."""

	mels, labels = batch
	mels = mels.to(device)
	labels = labels.to(device)

	outs = model(mels)

	loss = criterion(outs, labels)

	# Get the speaker id with highest probability.
	preds = outs.argmax(1)
	# Compute accuracy.
	accuracy = torch.mean((preds == labels).float())

	return loss, accuracy

"""# Validate
- Calculate accuracy of the validation set.
"""

from tqdm import tqdm
import torch


def valid(dataloader, model, criterion, device):
	"""Validate on validation set."""

	model.eval()
	running_loss = 0.0
	running_accuracy = 0.0
	# unit=" uttr": 指定了进度条的单位，这里为"uttr"，表示每一步的单位为样本数量
	pbar = tqdm(total=len(dataloader.dataset), ncols=0, desc="Valid", unit=" uttr")

	for i, batch in enumerate(dataloader):
		with torch.no_grad():
			loss, accuracy = model_fn(batch, model, criterion, device)
			running_loss += loss.item()
			running_accuracy += accuracy.item()

		# 每次更新进度条时，将当前进度增加当前批次中的样本数量，以反映当前已处理的样本数量
		pbar.update(dataloader.batch_size)
		pbar.set_postfix(
			val_loss=f"{running_loss / (i+1):.2f}",
			val_accuracy=f"{running_accuracy / (i+1):.2f}",
		)

	pbar.close()
	model.train()

	return running_accuracy / len(dataloader)

"""# Main function"""

from tqdm import tqdm
import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader, random_split

def parse_args():
	"""arguments"""
	config = {
		"data_dir": "./Dataset",
		"save_path": "model.ckpt",
		"batch_size": 32,
		"n_workers": 8,
		"valid_steps": 2000,
		"warmup_steps": 1000,
		"save_steps": 10000,
		"total_steps": 70000,
	}

	return config


def main(
	data_dir,
	save_path,
	batch_size,
	n_workers,
	valid_steps,
	warmup_steps,
	total_steps,
	save_steps,
):
	"""Main function."""
	device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
	print(f"[Info]: Use {device} now!")

	train_loader, valid_loader, speaker_num = get_dataloader(data_dir, batch_size, n_workers)
  # #iter()生成迭代器，以batch为单位遍历训练数据集中的数据 -逐批次地获取训练数据
	train_iterator = iter(train_loader)
	print(f"[Info]: Finish loading data!",flush = True)

	model = Classifier(n_spks=speaker_num).to(device)
	criterion = nn.CrossEntropyLoss()
  # 创建了一个 AdamW 优化器的实例，用来优化模型 model 的参数 -- lr=1e-3 表示初始化学习率为 0.001
	optimizer = AdamW(model.parameters(), lr=1e-3)
  # 自定义的学习率调度器函数
	scheduler = get_cosine_schedule_with_warmup(optimizer, warmup_steps, total_steps)
	print(f"[Info]: Finish creating model!",flush = True)

	best_accuracy = -1.0
	best_state_dict = None

	# desc="Train"：指定了进度条的描述，显示在进度条之前，用于描述当前进度条正在进行的任务。
	# unit=" step"：指定了进度条的单位，显示在进度条值的后面。表示每次更新进度条时，增加的单位数为一个step
	# total=valid_steps：指定了进度条的总步数，即每次更新进度条时，进度条的最大值。
	# ncols=0: 指定了进度条的宽度，这里设为0表示自动适应终端的宽
	pbar = tqdm(total=valid_steps, ncols=0, desc="Train", unit=" step")

	for step in range(total_steps): #一共运行total_Steps轮，这里没有epoch的概念
			# Get data
			try:
				# 训练数据迭代器 train_iterator 中获取下一个批次的数据，并将其赋值给变量 batch
				batch = next(train_iterator)
			# 如果当前迭代超过了 train_iterator 中的数据数量（即抛出了 StopIteration 异常），则重新初始化 train_iterator 并再次获取数据
			except StopIteration:
				train_iterator = iter(train_loader)
				batch = next(train_iterator)

			loss, accuracy = model_fn(batch, model, criterion, device)
			batch_loss = loss.item()
			batch_accuracy = accuracy.item()

			# Updata model --- 每一个batch/step更新一次参数
			loss.backward()
			optimizer.step()
			scheduler.step()
			optimizer.zero_grad()

			# Log
			# pbar.update() 方法用于更新进度条的进度，而 pbar.set_postfix() 方法则用于设置进度条的附加信息
			pbar.update()
			pbar.set_postfix(
				train_loss=f"{batch_loss:.2f}",
				train_accuracy=f"{batch_accuracy:.2f}",
				step=step + 1,
			)

			# Do validation --#经过valid_steps开始跑验证集所有数据哦
			# 通过验证集保存最优模型
			if (step + 1) % valid_steps == 0:
				pbar.close()

				valid_accuracy = valid(valid_loader, model, criterion, device)

				# keep the best model
				if valid_accuracy > best_accuracy:
					best_accuracy = valid_accuracy
					# 当前模型的状态字典保存到变量 best_state_dict
					best_state_dict = model.state_dict()

				pbar = tqdm(total=valid_steps, ncols=0, desc="Train", unit=" step")

			# Save the best model so far.
			if (step + 1) % save_steps == 0 and best_state_dict is not None:#每save_steps轮会保存一次当前最好模型
				torch.save(best_state_dict, save_path)
				# pbar.write() 方法来在进度条 pbar 下方显示一条消息
				pbar.write(f"Step {step + 1}, best model saved. (accuracy={best_accuracy:.4f})")

	pbar.close()

if __name__ == "__main__":
	main(**parse_args())

"""# Testing"""

import os
import json
import torch
from pathlib import Path
from torch.utils.data import Dataset


class InferenceDataset(Dataset):
	def __init__(self, data_dir):
		testdata_path = Path(data_dir) / "testdata.json"
		testdata = json.load(testdata_path.open())
		self.data_dir = data_dir
		self.data = testdata["utterances"]

	def __len__(self):
		return len(self.data)

	def __getitem__(self, index):
		utterance = self.data[index]
		feat_path = utterance["feature_path"]
		mel = torch.load(os.path.join(self.data_dir, feat_path))

		return feat_path, mel


def inference_collate_batch(batch):
	"""Collate a batch of data."""
	feat_paths, mels = zip(*batch)

	# torch.stack() 函数用于将张量列表进行堆叠，生成一个新的张量
	return feat_paths, torch.stack(mels)

"""## Main funcrion of Inference"""

import json
import csv
from pathlib import Path
from tqdm.notebook import tqdm

import torch
from torch.utils.data import DataLoader

def parse_args():
	"""arguments"""
	config = {
		"data_dir": "./Dataset",
		"model_path": "./model.ckpt",
		"output_path": "./output.csv",
	}

	return config


def main(
	data_dir,
	model_path,
	output_path,
):
	"""Main function."""
	device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
	print(f"[Info]: Use {device} now!")

	mapping_path = Path(data_dir) / "mapping.json"
	mapping = json.load(mapping_path.open())

	dataset = InferenceDataset(data_dir)
	dataloader = DataLoader(
		dataset,
		batch_size=1,
		shuffle=False,
		drop_last=False,
		num_workers=8,
		collate_fn=inference_collate_batch,
	)
	print(f"[Info]: Finish loading data!",flush = True)

	# 加载已保存的模型
	speaker_num = len(mapping["id2speaker"])
	model = Classifier(n_spks=speaker_num).to(device)
	model.load_state_dict(torch.load(model_path))
	model.eval()
	print(f"[Info]: Finish creating model!",flush = True)

	results = [["Id", "speakerid"]]
	for feat_paths, mels in tqdm(dataloader):
		with torch.no_grad():
			mels = mels.to(device)
			outs = model(mels)
			preds = outs.argmax(1).cpu().numpy()
			for feat_path, pred in zip(feat_paths, preds):
				results.append([feat_path, mapping["id2speaker"][str(pred)]])

	with open(output_path, 'w', newline='') as csvfile:
		# 创建一个 CSV 文件写入器对象，传入打开的文件对象 csvfile
		writer = csv.writer(csvfile)
	  # writerows() 方法会自动将每个子列表写入为 CSV 文件的一行
		writer.writerows(results)


if __name__ == "__main__":
	main(**parse_args())