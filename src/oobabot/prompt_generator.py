# purpose: generate a prompt for the AI to respond to, given
# the message history and persona.
import typing

from oobabot import templates
from oobabot.fancy_logging import get_logger
from oobabot.templates import TemplateStore
from oobabot.types import GenericMessage


class PromptGenerator:
    """
    Purpose: generate a prompt for the AI to use, given
    the message history and persona.
    """

    # this is set by the AI, and is the maximum length
    # it will understand before it starts to ignore
    # the rest of the prompt_prefix
    # note: we don't currently measure tokens, we just
    # count characters. This is a rough estimate.
    EST_CHARACTERS_PER_TOKEN = 3

    # the estimated number of characters in a line of message history
    # this is used to rougly calculate whether we'll have enough space
    # to supply the requested number of lines of history.
    #
    # in practice, we will look at the actual number of characters to
    # see what we can fit.
    #
    # note that we're doing calculations in characters, not in tokens,
    # so even counting characters exactly is still an estimate.
    EST_CHARACTERS_PER_HISTORY_LINE = 30

    # when we're not splitting responses, each history line is
    # much larger, and it's easier to run out of token space,
    # so we use a different estimate
    EST_CHARACTERS_PER_HISTORY_LINE_NOT_SPLITTING_RESPONSES = 180

    def __init__(
        self,
        ai_name: str,
        persona: str,
        history_lines: int,
        token_space: int,
        template_store: TemplateStore,
        dont_split_responses: bool,
    ):
        self.ai_name = ai_name
        self.persona = persona
        self.history_lines = history_lines
        self.token_space = token_space
        self.template_store = template_store
        self.dont_split_responses = dont_split_responses

        # this will be also used when sending message
        # to suppress sending the prompt text to the user
        self.bot_prompt_line = self.template_store.format(
            templates.Templates.PROMPT_HISTORY_LINE,
            {
                templates.TemplateToken.USER_NAME: self.ai_name,
                templates.TemplateToken.USER_MESSAGE: "",
            },
        ).strip()

        self.image_request_made = self.template_store.format(
            templates.Templates.PROMPT_IMAGE_COMING,
            {
                templates.TemplateToken.AI_NAME: self.ai_name,
            },
        )
        self._init_history_available_chars()

    def _init_history_available_chars(self) -> None:
        """
        Calculate the number of characters we have available
        for history, and raise an exception if we don't have
        enough.

        Raises:
            ValueError: if we don't estimate to have enough space
                for the requested number of lines of history
        """
        # the number of chars we have available for history
        # is:
        #   number of chars in token space (estimated)
        #   minus the number of chars in the prompt
        #     - without any history
        #     - but with the photo request
        #
        est_chars_in_token_space = self.token_space * self.EST_CHARACTERS_PER_TOKEN
        prompt_without_history = self._generate("", self.image_request_made)

        # how many chars might we have available for history?
        available_chars_for_history = est_chars_in_token_space - len(
            prompt_without_history
        )
        # how many chars do we need for the requested number of
        # lines of history?
        chars_per_history_line = self.EST_CHARACTERS_PER_HISTORY_LINE
        if self.dont_split_responses:
            chars_per_history_line = (
                self.EST_CHARACTERS_PER_HISTORY_LINE_NOT_SPLITTING_RESPONSES
            )

        required_history_size_chars = self.history_lines * chars_per_history_line

        if available_chars_for_history < required_history_size_chars:
            raise ValueError(
                "AI token space is too small for prompt_prefix and history "
                + "by an estimated "
                + f"{required_history_size_chars - available_chars_for_history}"
                + " characters.  You may lose history context.  You can save space"
                + " by shortening the persona or reducing the requested number of"
                + " lines of history."
            )
        self.max_history_chars = available_chars_for_history

    async def _render_history(
        self,
        ai_user_id: int,
        message_history: typing.AsyncIterator[GenericMessage],
        stop_before_message_id: int | None,
    ) -> str:
        # add on more history, but only if we have room
        # if we don't have room, we'll just truncate the history
        # by discarding the oldest messages first
        # this is s
        # it will understand before ignore
        #
        prompt_len_remaining = self.max_history_chars

        # history_lines is newest first, so figure out
        # how many we can take, then append them in
        # reverse order
        history_lines = []

        async for message in message_history:
            # if we've hit the throttle message, stop and don't add any
            # more history
            if stop_before_message_id and message.message_id == stop_before_message_id:
                break

            adjusted_author_name = message.author_name
            if message.author_id == ai_user_id:
                # make sure the AI always sees its persona name
                # in the transcript, even if the chat program
                # has it under a different account name
                adjusted_author_name = self.ai_name

                # hack: if the message includes the text
                # "tried to make an image with the prompt",
                # ignore it
                if "tried to make an image with the prompt" in message.body_text:
                    continue

            if not message.body_text:
                continue

            line = self.template_store.format(
                templates.Templates.PROMPT_HISTORY_LINE,
                {
                    templates.TemplateToken.USER_NAME: adjusted_author_name,
                    templates.TemplateToken.USER_MESSAGE: message.body_text,
                },
            )

            if len(line) > prompt_len_remaining:
                num_discarded_lines = self.history_lines - len(history_lines)
                get_logger().warn(
                    "ran out of prompt space, discarding "
                    + f"{num_discarded_lines} lines "
                    + "of chat history"
                )
                break

            prompt_len_remaining -= len(line)
            history_lines.append(line)

        history_lines.reverse()
        return "".join(history_lines)

    def _generate(
        self,
        message_history_txt: str,
        image_coming: str,
    ) -> str:
        prompt = self.template_store.format(
            templates.Templates.PROMPT,
            {
                templates.TemplateToken.AI_NAME: self.ai_name,
                templates.TemplateToken.PERSONA: self.persona,
                templates.TemplateToken.MESSAGE_HISTORY: message_history_txt,
                templates.TemplateToken.IMAGE_COMING: image_coming,
            },
        )
        # todo: make this part of the template?
        prompt += self.bot_prompt_line + "\n"
        return prompt

    async def generate(
        self,
        ai_user_id: int,
        message_history: typing.AsyncIterator[GenericMessage] | None,
        image_requested: bool,
        throttle_message_id: int,
    ) -> str:
        """
        Generate a prompt for the AI to respond to.
        """
        message_history_txt = ""
        if message_history is not None:
            message_history_txt = await self._render_history(
                ai_user_id, message_history, throttle_message_id
            )
        image_coming = self.image_request_made if image_requested else ""
        return self._generate(message_history_txt, image_coming)
