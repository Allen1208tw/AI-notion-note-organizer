import json
import unittest
from pathlib import Path

from src.processors.chapter_detector import detect_chapters


class ChapterDetectorTests(unittest.TestCase):
    def test_keeps_later_independent_chapter_sequence(self):
        text = "\n\n".join(
            [
                *(
                    f"Module {index}.\n"
                    f"Python 標題 {index}\n"
                    "這一章介紹 Python 基礎概念。"
                    for index in range(1, 11)
                ),
                "PyMySQL\nChapter1\nPyMySQL 介紹\n這一章介紹資料庫連線。",
                "PyMySQL\nChapter2\nINSERT / UPDATE\n這一章介紹新增與更新。",
                "PyMySQL\nChapter3\ndatetime 使用\n這一章介紹時間資料。",
                "PyMySQL\nChapter4\n實例練習\n這一章進行整合實作。",
            ]
        )

        chapters = detect_chapters(text)

        self.assertEqual(len(chapters), 14)
        self.assertEqual(
            [chapter["chapter_id"] for chapter in chapters],
            [str(index) for index in range(1, 15)],
        )
        self.assertEqual(chapters[10]["title"], "PyMySQL 介紹")
        self.assertEqual(chapters[11]["title"], "INSERT/UPDATE")
        self.assertEqual(chapters[12]["title"], "datetime 使用")
        self.assertEqual(chapters[13]["title"], "實例練習")

    def test_front_outline_defines_subsection_scope(self):
        text = """
Chapter 1.
線性代數
1.
向量
2.
內積
3.
矩陣
4.
語言模型運作

8
Section 1.
向量
向量與空間
向量內容
9
Section 2.
內積
內積內容
10
Section 3.
矩陣
矩陣內容
11
計算相關性
語言模型內容

Chapter 2.
微分
1.
深度學習優化策略
2.
微分
3.
偏微分與梯度
4.
連鎖律
5.
反向傳播
6.
記憶體管理

92
Loss 如何量化？
最佳化內容
93
平均變化率
微分內容
94
多變數最佳化問題
偏微分內容
95
連鎖律(Chain Rule)
連鎖律內容
96
反向傳播(Backpropagation)
反向傳播內容
97
記憶體瓶頸
記憶體內容

Chapter 3.
統計
Sec. 1 數據輪廓
1.
敘述性統計
2.
資料判讀
Sec. 2 模型評估
1.
迴歸模型
2.
分類模型

124
Section 1.
數據輪廓
數據內容
125
Section 2.
模型評估
模型內容
"""

        chapters = detect_chapters(text)

        self.assertEqual(len(chapters), 3)
        self.assertEqual(
            [section["title"] for section in chapters[0]["subsections"]],
            ["向量", "內積", "矩陣", "語言模型運作"],
        )
        self.assertEqual(
            [section["title"] for section in chapters[1]["subsections"]],
            [
                "深度學習優化策略",
                "微分",
                "偏微分與梯度",
                "連鎖律",
                "反向傳播",
                "記憶體管理",
            ],
        )
        self.assertEqual(
            [section["title"] for section in chapters[2]["subsections"]],
            ["數據輪廓", "模型評估"],
        )

    def test_fixture_chapter_and_subsection_formats(self):
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "chapter_detection_samples.json"
        )
        samples = json.loads(
            fixture_path.read_text(encoding="utf-8")
        )

        for sample in samples:
            with self.subTest(sample=sample["name"]):
                chapters = detect_chapters(sample["text"])
                expected_chapters = sample["expected_chapters"]

                self.assertEqual(
                    len(chapters),
                    len(expected_chapters),
                )

                self.assertEqual(
                    [chapter["title"] for chapter in chapters],
                    [
                        chapter["title"]
                        for chapter in expected_chapters
                    ],
                )

                self.assertEqual(
                    [
                        [
                            subsection["title"]
                            for subsection in chapter.get(
                                "subsections",
                                [],
                            )
                        ]
                        for chapter in chapters
                    ],
                    [
                        chapter["subsections"]
                        for chapter in expected_chapters
                    ],
                )


if __name__ == "__main__":
    unittest.main()
