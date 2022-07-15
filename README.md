
<div align='center'>

# NLHappy
<a href="https://pytorch.org/get-started/locally/"><img alt="PyTorch" src="https://img.shields.io/badge/PyTorch-ee4c2c?logo=pytorch&logoColor=white"></a>
<a href="https://pytorchlightning.ai/"><img alt="Lightning" src="https://img.shields.io/badge/-Lightning-792ee5?logo=pytorchlightning&logoColor=white"></a>
<a href="https://hydra.cc/"><img alt="Config: Hydra" src="https://img.shields.io/badge/Config-Hydra-89b8cd"></a>
<a href="https://github.com/ashleve/lightning-hydra-template"><img alt="Template" src="https://img.shields.io/badge/-Lightning--Hydra--Template-017F2F?style=flat&logo=github&labelColor=gray"></a>
<a href="https://spacy.io/"><img alt="Spacy" src="https://img.shields.io/badge/component-%20Spacy-blue"></a>
<a href="https://wandb.ai/"><img alt="WanDB" src="https://img.shields.io/badge/Log-WanDB-brightgreen"></a>
</div>
<br><br>

### 📌&nbsp;&nbsp; 简介

nlhappy是一款集成了数据处理,模型训练,文本处理流程构建等各种功能的自然语言处理库,相信通过nlhappy可以让你更愉悦的做各种nlp任务
> 它主要的依赖有
- [spacy](https://spacy.io/usage): 用于自然语言处理流程和组件构建
- [pytorch-lightning](https://pytorch-lightning.readthedocs.io/en/latest/): 用于模型的训练
- [datasets](https://huggingface.co/docs/datasets/index): 构建和分析训练数据
- [wandb](https://wandb.ai/): 训练日志以及训练结果统计
- [transformers](https://huggingface.co/docs/transformers/index): 预训练语言模型


### 🚀&nbsp;&nbsp; 安装
<details>
<summary><b>安装nlhappy</b></summary>

> 推荐先去[pytorch官网](https://pytorch.org/get-started/locally/)安装pytorch和对应cuda
```bash
# pip 安装
pip install -upgrade pip
pip install -upgrade nlhappy

# 通过poetry打包然后安装
# 首先将文件下载到本地
# 通过pipx 安装poetry
pip install -U pipx
pipx install poetry
pipx ensurepath 
# 需要重新打开命令行
poetry build
# 安装包 在dist文件夹
```
</details>

<details>
<summary><b>注册wandb</b></summary>

> wandb(用于可视化训练日志)
- 注册: https://wandb.ai/
- 获取认证: https://wandb.ai/authorize
- 登陆:
```bash
wandb login
```
模型训练开始后去[官网](https://wandb.ai/)查看训练实况
</details>




### ⚡&nbsp;&nbsp; 模型开发

<details>
<summary><b>文本分类</b></summary>

> 数据处理
```python
from nlhappy.utils.make_doc import Doc, DocBin
from nlhappy.utils.make_dataset import train_val_split
from nlhappy.utils.convert_doc import convert_docs_to_tc_dataset
import nlhappy
# 构建corpus
# 将数据处理为统一的Doc对象,它存储着所有标签数据
nlp = nlhappy
docs = []
# data为你自己的数据
# doc._.label 为文本的标签,之所以加'_'是因为这是spacy Doc保存用户自己数据的用法
for d in data:
    doc = nlp(d['text'])
    doc._.label = d['label']
    docs.append(doc)
# 保存corpus,方便后边badcase分析
db = DocBin(docs=docs, store_user_data=True)
# 新闻文本-Tag3为保存格式目录,需要更换为自己的形式
db.to_disk('corpus/TNEWS-Tag15/train.spacy')
# 构建数据集,为了训练模型
ds = convert_docs_to_tc_dataset(docs=docs)
# 你可以将数据集转换为dataframe进行各种分析,比如获取文本最大长度
df = ds.to_pandas()
max_length = df['text'].str.len().max()
# 数据集切分
dsd = train_val_split(ds, val_frac=0.2)
# 保存数据集,注意要保存到datasets/目录下
dsd.save_to_disk('datasets/TNEWS')
```
> 训练模型

编写训练脚本,scripts/train.sh
- 单卡
```
nlhappy \
datamodule=text_classification \
datamodule.dataset=TNEWS \
datamodule.plm=roberta-wwm-base \
datamodule.max_length=150 \
datamodule.batch_size=32 \
model=bert_tc \
model.lr=3e-5 \
seed=1234
# 默认为0号显卡,可以下代码可以修改显卡
# trainer.gpus=[1]
```
- 多卡
```
nlhappy \
datamodule=text_classification \
datamodule.dataset=TNEWS \
datamodule.plm=roberta-wwm-base \
datamodule.max_length=150 \
datamodule.batch_size=32 \
model=bert_tc \
model.lr=3e-5 \
trainer=ddp \
trainer.gpus=4 \
seed=123456
```

- 后台训练
```
nohup bash scripts/train.sh >/dev/null 2>&1 &
```
- 现在可以去[wandb官网](https://wandb.ai/)查看训练详情了, 并且会自动产生logs目录里面包含了训练的ckpt,日志等信息.
> 构建自然语言处理流程,并添加组件
```python
import nlhappy

nlp = nlhappy.nlp()
# 默认device cpu, 阈值0.8
config = {'device':'cuda:0', 'threshold':0.9}
tc = nlp.add_pipe('text_classifier', config=config)
# logs文件夹里面训练的模型路径
ckpt = 'logs/experiments/runs/TNEWS/date/checkpoints/epoch_score.ckpt/'
tc.init_model(ckpt)
text = '文本'
doc = nlp(text)
# 查看结果
print(doc.text, doc._.label, doc.cats)
# 保存整个流程
nlp.to_disk('path/nlp')
# 加载
nlp = nlhappy.load('path/nlp')
```
> badcase分析
```python
import nlhappy
from nlhappy.utils.make_doc import get_docs_form_docbin
from nlhappy.utils.analysis_doc import analysis_text_badcase, Example

targs = get_docs_from_docbin('corpus/TNEWS-Tag15/train.spacy')
nlp = nlhappy.load('path/nlp')
preds = []
for d in targs:
    doc = nlp(d['text'])
    preds.append(doc)
eg = [Example(x,y) for x,y in zip(preds, targs)]
badcases, score = analysis_text_badcase(eg, return_prf=True)
print(badcases[0].x, badcases[0].x._.label)
print(badcases[0].y, badcases[0].y._.label)
```
> 部署
- 直接用nlp开发接口部署
- 转为onnx
```python
from nlhappy.models import BertTextClassification
ckpt = 'logs/path/ckpt'
model = BertTextClassification.load_from_ckeckpoint(ckpt)
model.to_onnx('path/tc.onnx')
model.tokenizer.save_pretrained('path/tokenizer')
```
</details>

<details>
<summary><b>实体抽取</b></summary>
TODO
</details>

<details>
<summary><b>关系抽取</b></summary>
TODO
</details>

<details>
<summary><b>事件抽取</b></summary>
TODO
</details>

<details>
<summary><b>文本匹配</b></summary>
TODO
</details>

<details>
<summary><b>文本相似度</b></summary>
TODO
</details>








