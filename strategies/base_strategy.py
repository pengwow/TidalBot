class BaseStrategy:
    def __init__(self, params):
        self.params = params
        self.position = 0
        self.profit = 0.0

    def on_bar(self, bar):
        # 必须实现的回调方法
        pass

    def on_init(self):
        # 初始化逻辑
        pass