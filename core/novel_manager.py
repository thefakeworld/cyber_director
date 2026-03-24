#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
长篇小说播报管理器
==================
功能：
- 章节内容管理
- TTS音频生成
- 播放列表生成
- 进度追踪

注意：请确保使用合法授权的内容
"""

import json
import os
import subprocess
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Chapter:
    """章节"""
    id: int
    title: str
    content: str
    audio_path: Optional[str] = None
    duration: float = 0.0
    status: str = "pending"  # pending, generating, ready, playing, done


class NovelManager:
    """长篇小说播报管理器"""
    
    def __init__(self, novel_dir: Path):
        self.novel_dir = novel_dir
        self.novel_dir.mkdir(parents=True, exist_ok=True)
        
        self.chapters_file = self.novel_dir / "chapters.json"
        self.playlist_file = self.novel_dir / "novel_playlist.txt"
        self.progress_file = self.novel_dir / "progress.json"
        
        self.chapters: List[Chapter] = []
        self.current_chapter = 0
        
        self._load_chapters()
        self._load_progress()
    
    def _load_chapters(self):
        """加载章节"""
        if self.chapters_file.exists():
            with open(self.chapters_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.chapters = [Chapter(**c) for c in data]
    
    def _save_chapters(self):
        """保存章节"""
        with open(self.chapters_file, 'w', encoding='utf-8') as f:
            json.dump([vars(c) for c in self.chapters], f, ensure_ascii=False, indent=2)
    
    def _load_progress(self):
        """加载进度"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.current_chapter = data.get("current_chapter", 0)
    
    def _save_progress(self):
        """保存进度"""
        with open(self.progress_file, 'w', encoding='utf-8') as f:
            json.dump({
                "current_chapter": self.current_chapter,
                "updated_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
    
    def add_chapter(self, title: str, content: str) -> Chapter:
        """添加章节"""
        chapter_id = len(self.chapters) + 1
        chapter = Chapter(
            id=chapter_id,
            title=title,
            content=content
        )
        self.chapters.append(chapter)
        self._save_chapters()
        return chapter
    
    def generate_tts(self, chapter: Chapter, output_dir: Path) -> Optional[str]:
        """为章节生成TTS音频"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 分割长文本（每段不超过900字符）
        max_len = 900
        texts = []
        if len(chapter.content) > max_len:
            # 按段落分割
            paragraphs = chapter.content.split('\n\n')
            current = ""
            for p in paragraphs:
                if len(current) + len(p) < max_len:
                    current += p + "\n\n"
                else:
                    if current:
                        texts.append(current.strip())
                    current = p + "\n\n"
            if current:
                texts.append(current.strip())
        else:
            texts.append(chapter.content)
        
        # 生成各段音频
        audio_files = []
        for i, text in enumerate(texts):
            output_file = output_dir / f"chapter_{chapter.id:03d}_part{i+1}.wav"
            
            if output_file.exists():
                audio_files.append(str(output_file))
                continue
            
            chapter.status = "generating"
            self._save_chapters()
            
            print(f"  生成: 第{chapter.id}章 第{i+1}段...")
            
            cmd = [
                "z-ai", "tts",
                "-i", text,
                "-o", str(output_file),
                "-s", "0.85"  # 稍慢语速，适合故事播讲
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                if result.returncode == 0:
                    audio_files.append(str(output_file))
                else:
                    print(f"    ❌ TTS生成失败: {result.stderr[:200]}")
            except Exception as e:
                print(f"    ❌ 错误: {e}")
        
        # 合并音频文件
        if audio_files:
            combined_file = output_dir / f"chapter_{chapter.id:03d}.wav"
            
            if len(audio_files) == 1:
                # 单个文件，直接使用
                chapter.audio_path = audio_files[0]
            else:
                # 多个文件，合并
                concat_file = output_dir / f"chapter_{chapter.id:03d}_concat.txt"
                with open(concat_file, 'w') as f:
                    for af in audio_files:
                        f.write(f"file '{af}'\n")
                
                # 使用FFmpeg合并
                cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_file),
                    "-c", "copy",
                    str(combined_file)
                ]
                subprocess.run(cmd, capture_output=True, timeout=60)
                
                if combined_file.exists():
                    chapter.audio_path = str(combined_file)
                    # 清理临时文件
                    for af in audio_files:
                        Path(af).unlink(missing_ok=True)
                    concat_file.unlink(missing_ok=True)
                else:
                    chapter.audio_path = audio_files[0]  # 回退到第一个文件
            
            # 获取时长
            if chapter.audio_path:
                chapter.duration = self._get_audio_duration(chapter.audio_path)
                chapter.status = "ready"
            
            self._save_chapters()
            return chapter.audio_path
        
        return None
    
    def _get_audio_duration(self, audio_path: str) -> float:
        """获取音频时长"""
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return float(result.stdout.strip())
        except:
            return 0.0
    
    def generate_playlist(self, start_chapter: int = 0) -> Path:
        """生成播放列表"""
        with open(self.playlist_file, 'w') as f:
            for chapter in self.chapters[start_chapter:]:
                if chapter.audio_path and Path(chapter.audio_path).exists():
                    f.write(f"file '{chapter.audio_path}'\n")
        
        return self.playlist_file
    
    def get_total_duration(self) -> float:
        """获取总时长"""
        return sum(c.duration for c in self.chapters if c.status == "ready")
    
    def get_status_summary(self) -> Dict:
        """获取状态摘要"""
        return {
            "total_chapters": len(self.chapters),
            "ready_chapters": sum(1 for c in self.chapters if c.status == "ready"),
            "total_duration": self.get_total_duration(),
            "current_chapter": self.current_chapter,
            "current_title": self.chapters[self.current_chapter].title if self.chapters else None
        }


# =====================================================
# 示例：原创恐怖小说《古宅秘闻》
# =====================================================

ORIGINAL_HORROR_NOVEL = {
    "title": "古宅秘闻",
    "author": "AI创作",
    "chapters": [
        {
            "title": "第一章：神秘遗产",
            "content": """
林远从未想过，自己会继承一座百年古宅。

那是一个阴沉的下午，律师把一份厚厚的文件放在他面前。"这是您祖父留下的遗嘱，"律师推了推眼镜，"古宅位于青石镇，已经有八十年没有人居住了。"

林远翻看着文件，照片上的古宅被藤蔓覆盖，黑色的木质门窗紧闭，透着一股说不出的阴森。

"我祖父...为什么要留给我？"

律师沉默了一下："您祖父在遗嘱中说，这座宅子藏着一个秘密，只有林家血脉才能解开。而且..."律师停顿了一下，"他说，必须在七天之内去那里，否则后果自负。"

林远觉得莫名其妙，但既然是遗产，总不能不要。三天后，他开车来到了青石镇。

镇子很偏僻，导航最后一段甚至没有信号。他沿着老路开了一个多小时，终于在一座山脚下看到了那座古宅。

天已经黑了。古宅比照片上看起来更加破败，但奇怪的是，大门却是敞开的，像是有人在等他。

林远打着手电筒走进去，门厅里挂着厚厚的灰尘，地上落满了枯叶。他刚踏进门槛，身后的大门突然"砰"的一声关上了。

他猛地回头，只见门上贴着一张泛黄的纸条，上面用毛笔写着：

"欢迎回家，林家后人。记住，晚上十二点以后，不要上三楼。"
"""
        },
        {
            "title": "第二章：午夜脚步声",
            "content": """
林远在古宅里度过了第一夜。

他选择了二楼的一间卧室，虽然床铺陈旧，但勉强能睡。临睡前，他想起门上的纸条——晚上十二点以后不要上三楼。

这是恶作剧吗？还是...

凌晨三点，林远被一阵脚步声吵醒了。

"咚、咚、咚..."

声音来自楼上。三楼。

他躺在黑暗中，呼吸越来越急促。脚步声很慢，像是一个人在缓慢地踱步，来来回回，永不停歇。

"咚、咚、咚..."

大概过了半小时，脚步声终于消失了。林远一夜未眠。

第二天早上，他壮着胆子上到三楼。楼道尽头是一扇紧闭的门，门上挂着一把锈迹斑斑的锁。他试了试，锁是锁着的。

正当他准备离开时，突然发现门缝下露出一张纸条。他弯腰捡起来，上面写着：

"第三天，你会听到哭声。第五天，你会看到她。第七天，你会知道真相。"

林远感到一阵寒意从脊背升起。这些纸条是谁写的？为什么好像预知了未来？

他决定去镇上打听一下这座宅子的历史。

镇上的老人告诉他，这座宅子最早的主人姓林，就是他的曾祖父。八十年前，曾祖父的妹妹在宅子里失踪了，活不见人，死不见尸。从那以后，宅子就开始闹鬼。

"每到深夜，三楼就会传出脚步声，"老人压低声音说，"那是林小姐在找她的哥哥。她至死都没能见到他最后一面。"

林远的心沉了下去。他的祖父，为什么要把他引到这座充满怨念的宅子里？
"""
        },
        {
            "title": "第三章：消失的房间",
            "content": """
第三天夜里，哭声果然出现了。

起初是低低的啜泣，像是一个女人在极力压抑自己的悲伤。后来哭声越来越大，凄厉而绝望，回荡在整座宅子里。

林远躲在被子里，浑身发抖。他想逃离，但外面是荒山野岭，没有车根本走不了。而且，那份遗嘱里说，七天内必须完成什么，否则"后果自负"。

第四天，他在宅子里发现了一个奇怪的现象。

他清楚地记得，二楼走廊尽头有三扇门。但今天他数了数，只有两扇。多出来的那间房间...消失了。

他用手电筒仔细照着墙壁，发现墙上有一道细微的裂缝，像是被什么东西从里面封死了。

"你在找什么？"

一个声音突然在他身后响起。林远吓得差点摔倒，转身一看，是一个穿着民国时期旗袍的年轻女人，面容苍白，眼神空洞。

"你是谁？"林远的声音在发抖。

女人没有回答，只是幽幽地说："你还剩三天。三天之内，找不到钥匙，她就永远被困在里面了。"

"谁？被困在哪里？"

女人没有回答，身影渐渐变淡，最后消失在空气中。

林远这才意识到，他刚刚见到的，是...鬼。

那天晚上，他梦见了八十年前的情景。年轻的林小姐被关在一个房间里，她的哥哥站在门外，手里拿着一把钥匙，脸上带着诡异的笑容。

"你永远别想出来，"哥哥说，"遗产是我的，全是我的。"

林小姐在里面哭喊着，拍打着门，但门被牢牢锁住了。最后，她的哭声渐渐变弱，直至消失...

林远从梦中惊醒，浑身是冷汗。他终于明白了——他的曾祖父，为了独吞家产，把自己的妹妹活活关死在了那个房间里！

而那个房间，后来被他们用墙封死了。
"""
        },
        {
            "title": "第四章：真相",
            "content": """
第五天，林远开始寻找那把钥匙。

他翻遍了宅子里的每一个角落，最后在曾祖父的书房里发现了一个暗格。暗格里有一本发黄的日记，记录着当年的事情。

原来，林家祖上曾是当地的大户人家，家产丰厚。曾祖父和林小姐是龙凤胎，按照家规，家产应该两人平分。但曾祖父心胸狭窄，不愿意分家产给妹妹。

日记的最后几页写着：

"钥匙被我藏在了最安全的地方——三楼那扇门的后面。她永远也找不到，就像她永远出不来一样。"

林远终于明白了。钥匙藏在三楼，而那扇被封死的房间...也在三楼！

他鼓起勇气，再一次来到三楼。这一次，他仔细观察那扇紧锁的门后面的墙壁。

果然，在墙缝里，他摸到了一个冰冷的金属物件——一把锈迹斑斑的钥匙。

他颤抖着把钥匙插进门锁，"咔嚓"一声，锁开了。

门缓缓打开，里面是一个尘封了八十年的房间。房间中央，摆着一张梳妆台，台上放着一面镜子和一支簪子。

镜子里，映出了一个女人苍白的脸。

"谢谢你，"林小姐的声音在耳边响起，"八十年了，我终于可以离开了。"

她的身影渐渐变得透明，化作一道白光消失在窗外。

林远跌坐在地上，大口喘着气。一切都结束了...吗？

他想起遗嘱里的话——"只有林家血脉才能解开"。原来，曾祖父把妹妹害死后，良心受到谴责，立下遗嘱：只有后人解开这个秘密，让林小姐的冤魂得以安息，林家的血脉才能平安。

否则，林小姐的怨气会一直缠着林家的后代...

林远离开古宅时，回头看了一眼。大门依然敞开着，但这一次，门上的纸条变成了：

"谢谢你，林家后人。这座宅子，现在属于你了。"

阳光下，古宅不再阴森，藤蔓上开出了紫色的小花。

林远笑了。有些秘密，只有被揭开，才能真正消散。
"""
        },
        {
            "title": "第五章：新的开始",
            "content": """
一个月后，林远决定重新修缮古宅。

他请来了工人，把破旧的门窗换成新的，把长满青苔的屋顶翻修一遍，把荒草丛生的院子清理干净。

工人们干活的时候，林远在书房里找到了更多祖上留下的东西。一些老照片，几本账簿，还有一封从未寄出的信。

信是林小姐写的，收信人是她的未婚夫。信里说她哥哥最近行为古怪，她很担心，想问问未婚夫能不能提前来提亲，带她离开这个家。

可惜，这封信永远没能寄出去。

林远把信封好，决定去找找林小姐的未婚夫的后人。也许，他们还不知道这段往事。

经过一番打听，他终于在邻县找到了一户姓陈的人家。陈家的老人看到那封信，眼眶湿润了："我爷爷生前常说，他有个未婚妻，可惜在新婚前夜突然失踪了。他找了一辈子，到死都没能找到。"

林远把事情的真相告诉了他们。陈家人沉默了很久，最后说："能带我们去看看吗？"

秋日的午后，林远带着陈家人来到古宅。陈家的老人站在院子中央，望着那棵百年的老槐树，轻轻地说："爷爷，您的心愿，终于可以了结了。"

那天晚上，林远做了一个梦。

梦里，林小姐穿着嫁衣，和一个年轻男人站在槐树下。他们牵着手，笑容灿烂。

"谢谢你，"林小姐说，"让我们的故事，有了一个结局。"

林远醒来时，发现枕头上有一滴泪水。不是他的。

第二年春天，古宅焕然一新。林远没有把它卖掉，而是把它改造成了一间民宿，取名叫"忆林轩"。

每天都有客人来住，听林远讲那些古老的故事。孩子们在院子里跑来跑去，老人们坐在槐树下喝茶。

有一天晚上，林远听到二楼传来轻轻的脚步声。他没有害怕，只是对着空气说了一声："晚安，姑奶奶。"

脚步声停了一下，然后继续向前，最后消失在楼道的尽头。

从那以后，古宅再也没有闹过鬼。

但林远知道，林小姐还在那里，守护着这座宅子，守护着他们共同的家。

有些故事，以恐怖开始，却以温情结束。

这就是，古宅秘闻。
"""
        }
    ]
}


def create_novel_from_template(novel_dir: Path, novel_data: Dict) -> NovelManager:
    """从模板创建小说"""
    manager = NovelManager(novel_dir)
    
    # 清空现有章节
    manager.chapters = []
    
    # 添加章节
    for chapter_data in novel_data["chapters"]:
        manager.add_chapter(
            title=chapter_data["title"],
            content=chapter_data["content"].strip()
        )
    
    return manager


# =====================================================
# 测试代码
# =====================================================
if __name__ == "__main__":
    print("=" * 60)
    print("长篇小说播报管理器测试")
    print("=" * 60)
    
    # 创建小说目录
    novel_dir = Path("/home/z/my-project/cyber_director/assets/novels/guzhai")
    
    # 从模板创建
    manager = create_novel_from_template(novel_dir, ORIGINAL_HORROR_NOVEL)
    
    print(f"\n小说: {ORIGINAL_HORROR_NOVEL['title']}")
    print(f"作者: {ORIGINAL_HORROR_NOVEL['author']}")
    print(f"章节数: {len(manager.chapters)}")
    
    print("\n章节列表:")
    for chapter in manager.chapters:
        content_len = len(chapter.content)
        print(f"  第{chapter.id}章: {chapter.title} ({content_len}字)")
    
    # 生成摘要
    print("\n状态摘要:")
    summary = manager.get_status_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")
    
    print("\n" + "=" * 60)
