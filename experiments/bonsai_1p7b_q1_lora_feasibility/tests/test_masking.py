from copy import deepcopy

from pixie_bonsai.masking import AssistantOnlyCollator, encode_assistant_example


class FakeTokenizer:
    pad_token_id = 0
    eos_token_id = 2
    chat_template = "immutable-template"

    def apply_chat_template(self, messages, tokenize, add_generation_prompt, **kwargs):
        text = "<start>"
        for message in messages:
            text += f"<{message['role']}>{message['content']}"
        if add_generation_prompt:
            text += "<assistant>"
        else:
            text += "<eot>"
        return [3 + ord(character) for character in text]


def test_only_assistant_suffix_receives_loss() -> None:
    tokenizer = FakeTokenizer()
    before = deepcopy(tokenizer.__dict__)
    messages = [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "prompt"},
        {"role": "assistant", "content": "answer"},
    ]
    encoded = encode_assistant_example(tokenizer, messages, 256)
    first_supervised = next(index for index, label in enumerate(encoded["labels"]) if label != -100)
    assert first_supervised > 0
    assert all(label == -100 for label in encoded["labels"][:first_supervised])
    assert any(label != -100 for label in encoded["labels"])
    assert tokenizer.__dict__ == before


def test_left_truncation_keeps_supervised_response() -> None:
    tokenizer = FakeTokenizer()
    messages = [
        {"role": "user", "content": "p" * 500},
        {"role": "assistant", "content": "VISIBLE"},
    ]
    encoded = encode_assistant_example(tokenizer, messages, 32)
    assert len(encoded["input_ids"]) == 32
    assert any(label != -100 for label in encoded["labels"])


def test_collator_masks_padding() -> None:
    collator = AssistantOnlyCollator(0)
    batch = collator([
        {"input_ids": [1, 2], "attention_mask": [1, 1], "labels": [-100, 2]},
        {"input_ids": [1], "attention_mask": [1], "labels": [1]},
    ])
    assert batch["labels"].tolist() == [[-100, 2], [1, -100]]
    assert batch["attention_mask"].tolist() == [[1, 1], [1, 0]]


def test_batch_encoding_style_mapping_is_supported() -> None:
    class MappingTokenizer(FakeTokenizer):
        def apply_chat_template(self, *args, **kwargs):
            return {"input_ids": [super().apply_chat_template(*args, **kwargs)]}

    encoded = encode_assistant_example(MappingTokenizer(), [
        {"role": "user", "content": "prompt"},
        {"role": "assistant", "content": "answer"},
    ], 128)
    assert any(label != -100 for label in encoded["labels"])
