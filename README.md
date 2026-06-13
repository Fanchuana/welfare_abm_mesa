# WelfareABM Mesa

一个从零搭建的轻量多智能体福利社会仿真，用来对应 PPT 里的核心问题：政府在普惠福利和精准滴灌之间分配资源时，社会资产、贫困率、失业率和财政是否稳定。

## 这版保留的需求

- 政府：独立 `GovernmentAgent`，征收个人所得税、企业所得税，发放 UBI 和梯度精准补贴。
- 精准滴灌误差：默认 5%，包含穷人漏保和非贫困家庭骗保。
- 精准补贴资格：使用“工资收入 + 可用资产折算收入”的贫困评分，避免只看工资导致高资产老人也拿最高补贴。
- 企业：3-5 家企业，每期随机处于繁荣、稳定、衰退、萧条、复苏，影响工资和招聘容量。
- 家庭：单身青年、有孩家庭、老年家庭、无劳动能力家庭。
- 生命周期：年龄按季度增长、退休、死亡、单身青年组建有孩家庭、孩子成年后分出新家庭、年轻劳动力小概率丧失劳动能力。
- 指标：资产 Gini、收入 Gini、当期收入贫困率、资产审查贫困率、失业率、劳动参与率、平均工资、政府财政、福利支出。

## 暂时精简掉的复杂部分

- 房地产、租赁、空间地理和通勤。
- 完整婚配市场、生育决策和复杂家庭拆分合并。
- 商品价格市场、企业库存、银行信贷。
- 真实 census 数据校准。

这些部分 PolicySpace2 做得更重，但对课程大作业第一版不是必要项。

## 设计说明

- 一个 `step` 近似表示一个季度，而不是一年；这样 80 步约等于 20 年，能观察生命周期变化但不会让初始劳动人口过快退休。
- 家庭形成采用轻量规则：单身青年在 22-38 岁之间有概率转为有孩家庭；有孩家庭中的成年孩子有概率分出成为新的单身青年家庭。
- 政府财政允许赤字或盈余，用于观察不同福利政策下的财政可持续性压力；默认参数已通过小网格搜索调到税基与福利支出处于同一数量级。
- 家庭数量设置了上限，企业岗位会随家庭规模有弹性扩张，避免家庭分裂后劳动力供给暴涨导致失业率和资产 Gini 被机械推高。

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

## 后续可扩展方向

- 做政策组对比：纯 UBI、纯精准补贴、混合政策、不同误差率。
- 加 Mesa Solara 可视化界面。
- 借鉴 PolicySpace2 的家庭消费/企业雇佣更细规则。
- 加资产流向图：税收从家庭/企业流入政府，再由 UBI/精准补贴流回不同家庭类型。
