# WelfareABM Mesa
## 安装

推荐新环境：

```bash
cd /work/home/cryoem666/xyf/temp/pycharm/agent/welfare_abm_mesa
conda env create -f environment.yml
conda activate welfare-abm
```

或者用当前 Python：

```bash
pip install -r requirements.txt
```

## 运行

```bash
python scripts/run_simulation.py --steps 80 --seed 42 --households 220 --firms 4 --ubi 100 --error-rate 0.05
```

输出：

- `outputs/welfare_abm_metrics.csv`
- `outputs/welfare_abm_metrics.png`

政策对比：

```bash
python scripts/compare_policies.py
```

输出：

- `outputs/policy_comparison.csv`
- `outputs/policy_comparison.png`

参数校准：

```bash
python scripts/calibrate_policy.py
```

输出：

- `outputs/policy_calibration.csv`

校准脚本会扫描所得税率、企业税率、UBI 金额和精准补贴缩放比例，寻找财政不必然破产且 Gini 有改善的组合。当前默认参数采用较温和的校准结果：所得税 20%、企业税 28%、UBI 100、精准补贴三档为 90/60/30。

## 测试

```bash
pytest -q
```

当前最小测试覆盖政府独立 Agent、税收/福利执行、单身青年组建家庭、成年孩子分家。

## 可视化 Dashboard

Streamlit 交互版：

```bash
streamlit run app_streamlit.py --server.port 8501
```

打开 `http://127.0.0.1:8501`，可以在侧边栏调政策参数，查看单场景曲线和多政策对比。`False positive rate` 是骗保成功率，`False negative rate` 是穷人漏保率。

轻量标准库备用版：

```bash
python scripts/dashboard.py
```

打开 `http://127.0.0.1:8765`，可以调政策参数并重新运行仿真，页面会显示末期指标和 Gini、资产审查贫困率、失业率、政府财政曲线。

