import pandas as pd
import talib.abstract as ta
from strategies.base_strategy import BaseStrategy


class MovingAverageStrategy(BaseStrategy):
    """
    基于 TA-Lib 的简单移动平均（SMA）交叉策略
    配置参数：
        - short_window: 短期均线周期（默认5）
        - long_window: 长期均线周期（默认20）
    """

    def __init__(self, params: dict = None):
        super().__init__(params)
        self.short_window = self.params.get('short_window', 5)
        self.long_window = self.params.get('long_window', 20)
        self.validate_config({'short_window', 'long_window'})

    def signal(self, data: pd.Series) -> int:
        """
        生成交易信号
        :param data: 输入数据（需包含 'close' 列）
        :return: 信号值（1买/-1卖/0无）
        """
        if 'close' not in data:
            raise ValueError("数据必须包含 'close' 列")

        # 使用 TA-Lib 计算 SMA
        closes = data['close'].astype(float)
        short_sma = ta.SMA(closes, timeperiod=self.short_window)
        long_sma = ta.SMA(closes, timeperiod=self.long_window)

        # 获取最新信号
        latest_short = short_sma[-1]
        latest_long = long_sma[-1]

        if latest_short > latest_long:
            return 1  # 金叉，买入
        elif latest_short < latest_long:
            return -1  # 死叉，卖出
        else:
            return 0  # 持有

    def validate_config(self, required_keys: set) -> bool:
        # 检查所有必需的配置参数是否存在
        for key in required_keys:
            if key not in self.params:
                raise ValueError(f"缺少必需的配置参数: {key}")
        
        # 检查短期和长期均线周期的有效性
        if not (self.short_window > 0 and self.long_window > 0 and self.short_window < self.long_window):
            raise ValueError("短期均线周期必须小于长期均线周期，且两者都必须大于0")
        
        return True
