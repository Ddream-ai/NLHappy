import pytorch_lightning as pl
from transformers import BertModel, BertTokenizer
import torch.nn as nn
import torch
import os
from ...metrics.span import SpanF1
from ...utils.preprocessing import fine_grade_tokenize
from ...layers import MultiLabelCategoricalCrossEntropy, EfficientGlobalPointer
import srsly

class BertGlobalPointer(pl.LightningModule):
    def __init__(
        self,
        hidden_size: int,
        lr: float,
        weight_decay: float,
        dropout: float ,
        threshold: float = 0.5,
        **data_params
    ) : 
        super().__init__()
        self.save_hyperparameters()


        self.bert = BertModel(data_params['bert_config'])
        # 使用更加高效的GlobalPointer https://kexue.fm/archives/8877
        self.classifier = EfficientGlobalPointer(
            input_size=self.bert.config.hidden_size, 
            hidden_size=hidden_size,
            output_size=len(self.hparams.label2id))

        self.dropout = nn.Dropout(dropout)
        self.criterion = MultiLabelCategoricalCrossEntropy()

        self.train_f1 = SpanF1()
        self.val_f1 = SpanF1()
        self.test_f1 = SpanF1()

        self.tokenizer = self._init_tokenizer()


    def forward(self, input_ids, token_type_ids, attention_mask=None):
        x = self.bert(input_ids=input_ids, token_type_ids=token_type_ids, attention_mask=attention_mask).last_hidden_state
        x = self.dropout(x)
        logits = self.classifier(x, mask=attention_mask)
        return logits


    def on_train_start(self) -> None:
        state_dict = torch.load(self.hparams.pretrained_dir + self.hparams.pretrained_model + '/pytorch_model.bin')
        self.bert.load_state_dict(state_dict)
        self.print(f'{self.hparams.pretrained_dir + self.hparams.pretrained_model} loaded')


    def shared_step(self, batch):
        inputs, span_ids = batch['inputs'], batch['span_ids']
        logits = self(**inputs)
        pred = logits.ge(self.hparams.threshold).float()
        batch_size, ent_type_size = logits.shape[:2]
        y_true = span_ids.reshape(batch_size*ent_type_size, -1)
        y_pred = logits.reshape(batch_size*ent_type_size, -1)
        loss = self.criterion(y_pred, y_true)
        return loss, pred, span_ids


    def training_step(self, batch, batch_idx):
        loss, pred, true = self.shared_step(batch)
        self.train_f1(pred, true)
        self.log('train/f1', self.train_f1, on_step=True, on_epoch=True, prog_bar=True)
        return {'loss': loss}


    def validation_step(self, batch, batch_idx):
        loss, pred, true = self.shared_step(batch)
        self.val_f1(pred, true)
        self.log('val/f1', self.val_f1, on_step=False, on_epoch=True, prog_bar=True)
        return {'loss': loss}


    def test_step(self, batch, batch_idx):
        loss, pred, true = self.shared_step(batch)
        self.test_f1(pred, true)
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
             'lr': self.hparams.lr * 5, 'weight_decay': self.hparams.weight_decay},
            {'params': [p for n, p in self.classifier.named_parameters() if any(nd in n for nd in no_decay)],
             'lr': self.hparams.lr * 5, 'weight_decay': 0.0}
        ]
        self.optimizer = torch.optim.AdamW(grouped_parameters)
        self.scheduler = torch.optim.lr_scheduler.LambdaLR(self.optimizer, lambda epoch: 1.0 / (epoch + 1.0))
        return [self.optimizer], [self.scheduler]

    def _init_tokenizer(self):
        with open('./vocab.txt', 'w') as f:
            for k in self.hparams.token2id.keys():
                f.writelines(k + '\n')
        self.hparams.bert_config.to_json_file('./config.json')
        tokenizer = BertTokenizer.from_pretrained('./')
        os.remove('./vocab.txt')
        os.remove('./config.json')
        return tokenizer


    def predict(self, text: str, device: str):
        tokens = fine_grade_tokenize(text, self.tokenizer)
        inputs = self.tokenizer.encode_plus(
            tokens,
            is_pretokenized=True,
            add_special_tokens=True,
            return_tensors='pt')
        inputs.to(device)
        logits = self(**inputs)
        spans_ls = torch.nonzero(logits>self.hparams.threshold).tolist()
        spans = []
        for span in spans_ls :
            start = span[2]
            end = span[3]
            spans.append([start-1, end-1, self.hparams.id2label[span[1]], text[start-1:end]])
        return spans



        

    


        


    

    
        
