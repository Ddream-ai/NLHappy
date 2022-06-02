import torch
from pytorch_lightning import LightningModule
from torchmetrics import F1Score
from typing import List, Any
from transformers import BertModel, BertTokenizer
from ...layers.classifier import SimpleDense
from typing import List, Dict
import os
import torch.nn.functional as F

class BertTextClassification(LightningModule):
    '''
    文本分类模型
    '''
    def __init__(self, 
                hidden_size: int ,
                lr: float ,
                weight_decay: float ,
                dropout: float,
                **kwargs):
        super(BertTextClassification, self).__init__()  
        self.save_hyperparameters()

        # 模型架构
        self.bert = BertModel(self.hparams['trf_config'])
        self.classifier = SimpleDense(self.bert.config.hidden_size, hidden_size, len(self.hparams.label2id))
        self.dropout = torch.nn.Dropout(dropout)
        
        # 损失函数
        self.criterion = torch.nn.CrossEntropyLoss()

        # 评价指标
        self.train_f1 = F1Score(num_classes=len(self.hparams.label2id), average='macro')
        self.val_f1= F1Score(num_classes=len(self.hparams.label2id), average='macro')
        self.test_f1 = F1Score(num_classes=len(self.hparams.label2id), average='macro')

        # 预处理tokenizer
        self.tokenizer = self._init_tokenizer()

    def forward(self, input_ids, token_type_ids, attention_mask):
        x = self.bert(input_ids=input_ids, token_type_ids=token_type_ids, attention_mask=attention_mask)
        x = x.last_hidden_state[:, 0]
        logits = self.classifier(x)  # (batch_size, output_size)
        return logits
    


    def on_train_start(self) -> None:
        plm_path = os.path.join(self.hparams.plm_dir ,self.hparams.plm, 'pytorch_model.bin')
        state_dict = torch.load(plm_path)
        self.print(f'load pretrained model from {plm_path}')
        self.bert.load_state_dict(state_dict)
        
    def shared_step(self, batch):
        inputs = batch['inputs']
        label_ids = batch['label_ids']
        logits = self(**inputs)
        loss = self.criterion(logits, label_ids)
        pred_ids = torch.argmax(logits, dim=-1)
        return loss, pred_ids, label_ids

    def training_step(self, batch, batch_idx):
        loss, pred_ids, label_ids = self.shared_step(batch)
        self.train_f1(pred_ids, label_ids)
        self.log('train/f1', self.train_f1, on_step=True, on_epoch=True, prog_bar=True)
        return {'loss': loss}
    
    def validation_step(self, batch, batch_idx):
        loss, pred_ids, label_ids = self.shared_step(batch)
        self.val_f1(pred_ids, label_ids)
        self.log('val/f1', self.val_f1, on_step=False, on_epoch=True, prog_bar=True)
        return {'loss': loss}

    def test_step(self, batch, batch_idx):
        loss, pred_ids, label_ids = self.shared_step(batch)
        self.test_f1(pred_ids, label_ids)
        self.log('test/f1', self.test_f1, on_step=False, on_epoch=True, prog_bar=True)
        return {'loss': loss}
    
    def configure_optimizers(self):
        no_decay = ['bias', 'LayerNorm.bias', 'LayerNorm.weight']
        grouped_parameters = [
            {'params': [p for n, p in self.bert.named_parameters() if not any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr, 'weight_decay': self.hparams.weight_decay},
            {'params': [p for n, p in self.bert.named_parameters() if any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr, 'weight_decay': 0.0},
            {'params': [p for n, p in self.classifier.named_parameters() if not any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr *5, 'weight_decay': self.hparams.weight_decay},
            {'params': [p for n, p in self.classifier.named_parameters() if any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr * 10, 'weight_decay': 0.0}
        ]
        optimizer = torch.optim.AdamW(grouped_parameters)
        scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda epoch: 1.0 / (epoch + 1.0))
        return [optimizer], [scheduler]


    def predict(self, text: str, device: str='cpu') -> Dict[str, float]:
        device = torch.device(device)
        inputs = self.tokenizer(
                text,
                padding='max_length',
                max_length=self.hparams.max_length,
                return_tensors='pt',
                truncation=True)
        inputs.to(device)
        # self.to(device)
        # self.freeze()
        self.eval()
        with torch.no_grad():
            logits = self(**inputs)
            scores = torch.nn.functional.softmax(logits, dim=-1).tolist()
            cats = {}
            for i, v in enumerate(scores[0]):   # scores : [[0.1, 0.2, 0.3, 0.4]]
                cats[self.hparams.id2label[i]] = v
        return sorted(cats.items(), key=lambda x: x[1], reverse=True)

    def _init_tokenizer(self):
        with open('./vocab.txt', 'w') as f:
            for k in self.hparams.vocab.keys():
                f.writelines(k + '\n')
        self.hparams.trf_config.to_json_file('./config.json')
        tokenizer = BertTokenizer.from_pretrained('./')
        os.remove('./vocab.txt')
        os.remove('./config.json')
        return tokenizer

