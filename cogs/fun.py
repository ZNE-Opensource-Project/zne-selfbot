import asyncio
import datetime
import io
import json
import os
import random
import re
import string
import textwrap
import aiohttp
import discord
from discord.ext import commands
from typing import Optional, List, Tuple


class FunCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    async def _delete_invoke(self, ctx) -> None:
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.NotFound):
            pass

    async def _api_get(self, url: str, params: dict = None, headers: dict = None) -> Optional[dict]:
        try:
            async with self.session.get(
                url, params=params, headers=headers, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None

    async def _api_get_text(self, url: str) -> Optional[str]:
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.text()
                return None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None

    async def _resolve_user(self, ctx, arg: str) -> Optional[discord.abc.User]:
        if arg is None:
            return None
        member_conv = commands.MemberConverter()
        try:
            return await member_conv.convert(ctx, arg)
        except Exception:
            pass
        user_conv = commands.UserConverter()
        try:
            return await user_conv.convert(ctx, arg)
        except Exception:
            pass
        return None

    @staticmethod
    def _random_ip() -> str:
        return f"{random.randint(1,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"

    # ------------------------------------------------------------------ #
    # Hardcoded data arrays
    # ------------------------------------------------------------------ #
    EIGHTBALL_RESPONSES = [
        "It is certain.", "It is decidedly so.", "Without a doubt.",
        "Yes definitely.", "You may rely on it.", "As I see it, yes.",
        "Most likely.", "Outlook good.", "Yes.", "Signs point to yes.",
        "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
        "Cannot predict now.", "Concentrate and ask again.",
        "Don't count on it.", "My reply is no.", "My sources say no.",
        "Outlook not so good.", "Very doubtful."
    ]

    INSULTS = [
        "You're not stupid; you just have bad luck thinking.",
        "If I threw a stick, you'd chase it.",
        "You bring everyone so much joy when you leave the room.",
        "I'd agree with you but then we'd both be wrong.",
        "You're like a cloud. When you disappear, it's a beautiful day.",
        "Your secrets are safe with me. I never listen.",
        "I've seen salads more intimidating than you.",
        "You're the reason God created the middle finger.",
        "Somewhere out there, a tree is producing oxygen for you. Apologize to it.",
        "You have the right to remain silent because whatever you say is probably stupid.",
        "I'm not insulting you. I'm describing you.",
        "You're not the dumbest person alive, but you better hope they don't die.",
        "If ignorance is bliss, you must be the happiest person alive.",
        "You have an entire life to be a jerk. Take today off.",
        "I'd explain it to you but I left my crayons at home.",
        "You're proof that evolution can go in reverse.",
        "Roses are red, violets are blue, I have five fingers, the middle one's for you.",
        "You're the human equivalent of a participation trophy.",
        "You look like something I drew with my left hand.",
        "I thought of you today. It reminded me to take out the trash.",
        "You're not pretty enough to be this stupid.",
        "The last time I saw something like you, I flushed it.",
        "You're impossible to underestimate.",
        "If you were any more inbred, you'd be a sandwich.",
        "Your family tree must be a cactus because everyone on it is a prick."
    ]

    DAD_JOKES = [
        "Why don't scientists trust atoms? Because they make up everything.",
        "What do you call a fake noodle? An impasta.",
        "I'm afraid for the calendar. Its days are numbered.",
        "What do you call a belt made of watches? A waist of time.",
        "Why did the scarecrow win an award? He was outstanding in his field.",
        "How do you organize a space party? You planet.",
        "What did the ocean say to the beach? Nothing, it just waved.",
        "Why can't a nose be 12 inches long? Because then it would be a foot.",
        "What's orange and sounds like a parrot? A carrot.",
        "Why did the bicycle fall over? It was two tired.",
        "What do you call a boomerang that won't come back? A stick.",
        "I used to play piano by ear, but now I use my hands.",
        "What do you call a cow with no legs? Ground beef.",
        "Why do dads tell such bad jokes? They have groan-up humor.",
        "What's a skeleton's favorite instrument? A trom-bone.",
        "Why did the golfer bring two pants? In case he got a hole in one.",
        "How do you make holy water? Boil the hell out of it.",
        "I told my wife she should embrace her mistakes. She gave me a hug.",
        "Parallel lines have so much in common. Too bad they'll never meet.",
        "What's a banana peel's favorite dance? The slip.",
        "Why don't eggs tell each other secrets? They'd crack each other up.",
        "What's red and bad for your teeth? A brick.",
        "Why did the math book look sad? It had too many problems.",
        "I'm reading a book about anti-gravity. It's impossible to put down.",
        "How does the moon cut his hair? Eclipse it."
    ]

    YO_MOMMA_JOKES = [
        "Yo momma's so fat, when she sat on an iPhone, it turned into an iPad.",
        "Yo momma's so old, her birth certificate says expired.",
        "Yo momma's so slow, she took 2 hours to watch 60 Minutes.",
        "Yo momma's so fat, she doesn't need the internet. She's already world wide.",
        "Yo momma's so stupid, she tried to climb Mountain Dew.",
        "Yo momma's so poor, she can't even pay attention.",
        "Yo momma's so ugly, she made One Direction go another direction.",
        "Yo momma's so fat, her blood type is Ragu.",
        "Yo momma's so hairy, Bigfoot took a picture of her.",
        "Yo momma's so old, she knew Burger King when he was a prince.",
        "Yo momma's so fat, she jumped in the ocean and washed up on three continents.",
        "Yo momma's so stupid, she put two quarters in her ears and thought she was listening to 50 Cent.",
        "Yo momma's so fat, she uses Google Earth to take selfies.",
        "Yo momma's so ugly, when she looked in the mirror, her reflection said 'no thanks'.",
        "Yo momma's so short, she can do pull-ups on a curb.",
        "Yo momma's so fat, she sat on a dollar and made change.",
        "Yo momma's so poor, ducks throw bread at her.",
        "Yo momma's so ugly, her portraits hang themselves.",
        "Yo momma's so fat, the back of her neck looks like a pack of hot dogs.",
        "Yo momma's so stupid, she thought Taco Bell was a Mexican phone company.",
        "Yo momma's so old, her social security number is 1.",
        "Yo momma's so dirty, she washes her hands BEFORE going to the bathroom.",
        "Yo momma's so nasty, the trash can won't take her out.",
        "Yo momma's so fat, when she wears a yellow coat, people yell 'TAXI!'.",
        "Yo momma's so bald, her head looks like a potato someone forgot in the cupboard."
    ]

    WOULD_YOU_RATHER = [
        "Would you rather always have to sing instead of speaking, or always have to whisper?",
        "Would you rather have fingers as long as your legs, or legs as long as your fingers?",
        "Would you rather live without music or live without movies?",
        "Would you rather be able to teleport but only once a day, or fly but only 10 feet off the ground?",
        "Would you rather have a rewind button for your life, or a pause button?",
        "Would you rather always know when someone is lying, or always get away with lying?",
        "Would you rather have unlimited pizza or unlimited sushi?",
        "Would you rather never have to sleep or never have to eat?",
        "Would you rather be the funniest person alive or the smartest person alive?",
        "Would you rather be able to read minds or see the future?",
        "Would you rather have a personal robot or a personal chef?",
        "Would you rather live in a treehouse or a cave?",
        "Would you rather have no one show up to your wedding or no one show up to your funeral?",
        "Would you rather be famous but poor, or rich but unknown?",
        "Would you rather have the ability to talk to animals or speak every human language?",
        "Would you rather age backwards or age normally but live to 200?",
        "Would you rather breathe underwater or survive in space without a suit?",
        "Would you rather be invisible or have super strength?",
        "Would you rather have a rewind button or a fast-forward button?",
        "Would you rather lose your sense of taste or your sense of smell?",
        "Would you rather fight 100 duck-sized horses or 1 horse-sized duck?",
        "Would you rather have unlimited wifi or unlimited battery?",
        "Would you rather always be 10 minutes late or always be 20 minutes early?",
        "Would you rather have a photographic memory or be able to forget anything at will?",
        "Would you rather only be able to whisper or only be able to shout?"
    ]

    TOPICS = [
        "If you could have any superpower, what would it be and why?",
        "What's the most unusual food you've ever eaten?",
        "If you could time travel to any era, where would you go?",
        "What's your biggest pet peeve?",
        "If you could switch lives with one person for a day, who would it be?",
        "What's the best piece of advice you've ever received?",
        "If you won the lottery, what's the first thing you'd buy?",
        "What's a skill you wish you had?",
        "What's your favorite childhood memory?",
        "If you could live anywhere in the world, where would it be?",
        "What's the weirdest dream you've ever had?",
        "If you could meet any historical figure, who would it be?",
        "What's the most adventurous thing you've ever done?",
        "What's a movie you can watch over and over?",
        "If animals could talk, which one would be the rudest?",
        "What's something you believed as a kid that seems ridiculous now?",
        "If you could only eat one food for the rest of your life, what would it be?",
        "What's your idea of a perfect day?",
        "If you could instantly master any instrument, which would you pick?",
        "What's the worst fashion trend you ever followed?",
        "If you could have dinner with any three people, dead or alive, who?",
        "What's the most useless talent you have?",
        "If your life was a book, what would the title be?",
        "What's something you wish you knew 10 years ago?",
        "If you could eliminate one thing from your daily routine, what would it be?"
    ]

    ADVICE = [
        "Never trust a fart.",
        "If you're going through hell, keep going.",
        "Don't set yourself on fire to keep others warm.",
        "The early bird gets the worm, but the second mouse gets the cheese.",
        "Before you criticize someone, walk a mile in their shoes. That way, you're a mile away and you have their shoes.",
        "Life is short. Smile while you still have teeth.",
        "Don't take life too seriously. You'll never get out alive.",
        "If at first you don't succeed, skydiving is not for you.",
        "A clear conscience is usually the sign of a bad memory.",
        "Never miss a good chance to shut up.",
        "Always borrow money from a pessimist. They won't expect it back.",
        "Knowledge is knowing a tomato is a fruit. Wisdom is not putting it in a fruit salad.",
        "To steal ideas from one person is plagiarism. To steal from many is research.",
        "The only thing worse than a knee-jerk reaction is a no-knee jerk reaction.",
        "If you think nobody cares if you're alive, try missing a few payments.",
        "Before you marry a person, you should first make them use a computer with slow internet to see who they really are.",
        "You can't have everything. Where would you put it?",
        "The road to success is always under construction.",
        "Age is just a number. In prison, it's also a sentence.",
        "Don't worry about what people think. They don't do it very often.",
        "Always get your revenge in the most petty, inconvenient way possible.",
        "If you lend someone $20 and never see them again, it was worth it.",
        "The best time to plant a tree was 20 years ago. The second best time is now. Unless it's winter. Then wait.",
        "Never argue with stupid people. They'll drag you down to their level and beat you with experience.",
        "Remember: when you're dead, you don't know it. It's only painful for others. Same when you're stupid."
    ]

    CAT_FACTS = [
        "Cats sleep for 70% of their lives.",
        "A group of cats is called a clowder.",
        "Cats can't taste sweetness.",
        "A cat's nose print is unique, like a human fingerprint.",
        "Cats have 32 muscles in each ear.",
        "The oldest known pet cat existed 9,500 years ago.",
        "Cats can jump up to 6 times their length.",
        "A cat's purr vibrates at 25-150 Hz, which can promote healing.",
        "Cats walk like camels and giraffes: both right feet, then both left feet.",
        "A cat's brain is 90% similar to a human's.",
        "Cats have a third eyelid called the haw.",
        "The richest cat in the world inherited $13 million.",
        "Cats meow only to communicate with humans, not other cats.",
        "A cat can run up to 30 mph in short bursts.",
        "The technical term for a hairball is a 'bezoar'.",
        "Cats are lactose intolerant despite the stereotype.",
        "A cat's collarbone is not connected to other bones.",
        "Abraham Lincoln kept four cats in the White House."
    ]

    DOG_FACTS = [
        "Dogs have three eyelids.",
        "A dog's sense of smell is 40x better than a human's.",
        "Dogs can learn over 1,000 words.",
        "The Labrador Retriever has been the most popular breed for 30 years.",
        "Dogs' noses are wet to help absorb scent chemicals.",
        "Greyhounds can reach speeds of 45 mph.",
        "Dogs dream just like humans do.",
        "The Basenji is the only barkless dog breed.",
        "Dogs have 18 muscles to move their ears.",
        "A dog's fingerprint is its nose print.",
        "Puppies are born blind and deaf.",
        "Dogs curl up in a ball to protect their organs while sleeping.",
        "The world's oldest dog lived to be 30 years old.",
        "Dogs can detect diseases like cancer through smell.",
        "Three dogs survived the Titanic sinking.",
        "A dog's normal body temperature is 101.2°F.",
        "The tallest dog ever was a Great Dane named Zeus at 44 inches."
    ]

    PANDA_FACTS = [
        "Pandas spend 10-16 hours a day eating bamboo.",
        "A newborn panda is about the size of a stick of butter.",
        "Giant pandas have a pseudo-thumb, an extended wrist bone for gripping bamboo.",
        "Pandas are born pink, blind, and hairless.",
        "An adult panda can eat 12-38 kg of bamboo daily.",
        "Pandas can swim and climb trees very well.",
        "A panda's diet is 99% bamboo, but they are technically carnivores.",
        "Wild pandas live mainly in the mountains of central China.",
        "Pandas communicate by scent-marking trees and rocks.",
        "A panda's bite is stronger than a lion's relative to body size.",
        "Pandas have black patches around their eyes that are unique like fingerprints.",
        "Female pandas are only fertile for 2-3 days a year.",
        "There are fewer than 2,000 giant pandas left in the wild.",
        "Pandas release a weak 'bleat' sound instead of roaring.",
        "Baby pandas don't open their eyes until they are 6-8 weeks old.",
        "The red panda is actually more closely related to raccoons than to giant pandas."
    ]

    FOX_FACTS = [
        "Foxes belong to the same family as dogs, wolves, and jackals.",
        "A group of foxes is called a 'skulk' or 'leash'.",
        "Foxes use the Earth's magnetic field to hunt like a compass.",
        "Red foxes can hear a watch ticking 40 yards away.",
        "Foxes have whiskers on their legs as well as their faces.",
        "A fox's tail makes up about a third of its length.",
        "Arctic foxes change color with the seasons, from brown to white.",
        "Foxes are omnivores and eat fruit, insects, small mammals, and birds.",
        "Fennec foxes have the largest ears relative to body size of any canid.",
        "Foxes can run up to 30 mph.",
        "Male foxes are called dogs or reynards; females are vixens.",
        "Foxes can make over 40 different sounds.",
        "Urban foxes often have shorter lifespans than rural ones.",
        "A fox's pupils are vertical like a cat's.",
        "Baby foxes are called kits, cubs, or pups.",
        "Foxes cache extra food by burying it for later."
    ]

    KOALA_FACTS = [
        "Koalas sleep up to 18-22 hours a day.",
        "Koalas have fingerprints almost identical to human ones.",
        "A koala's diet is almost entirely eucalyptus leaves.",
        "Koalas have a special stomach chamber to detoxify eucalyptus.",
        "Baby koalas are called joeys and live in the mother's pouch.",
        "Koalas are marsupials, not bears.",
        "A koala's brain is small and smooth to save energy.",
        "Koalas rarely drink water; they get moisture from leaves.",
        "Each koala has a home range of eucalyptus trees it marks with scent.",
        "Koalas have two thumbs on each front paw.",
        "A koala's call can carry over a kilometer.",
        "Koalas communicate through bellows that sound like snoring.",
        "Joeys eat a special poop called 'pap' to gain gut bacteria.",
        "Koalas have poor vision but a strong sense of smell.",
        "A koala's nose is leathery and hairless to help it sniff leaves.",
        "Wild koalas live about 10-12 years."
    ]

    BIRD_FACTS = [
        "Birds are the only animals with feathers.",
        "The bee hummingbird is the smallest bird, weighing less than a penny.",
        "An ostrich's eye is bigger than its brain.",
        "Some birds, like crows, use tools and recognize human faces.",
        "The wandering albatross has the largest wingspan of any bird.",
        "Penguins are birds that cannot fly but swim excellently.",
        "A chicken can live without its head for minutes to hours.",
        "Birds have hollow bones to make flight easier.",
        "The fastest bird, the peregrine falcon, dives at over 200 mph.",
        "Some parrots can live over 80 years.",
        "Birds evolved from theropod dinosaurs.",
        "A group of flamingos is called a 'flamboyance'.",
        "Ravens can mimic human speech better than some parrots.",
        "Birds don't have a bladder; they excrete uric acid as a paste.",
        "The common swift can stay airborne for up to 10 months.",
        "Owls can rotate their heads about 270 degrees."
    ]

    REDPANDA_FACTS = [
        "Red pandas are not closely related to giant pandas.",
        "They are the only living members of their own family, Ailuridae.",
        "Red pandas use their striped tails for balance and warmth.",
        "Red pandas are excellent climbers and sleep in trees.",
        "They mostly eat bamboo but also fruit, eggs, and insects.",
        "Red pandas are mostly solitary and nocturnal.",
        "A red panda's 'false thumb' is an extended wrist bone.",
        "Baby red pandas are called cubs and are born blind.",
        "Red pandas communicate with squeaks, twitters, and hisses.",
        "They have semi-retractable claws for gripping branches.",
        "Red pandas mark territory with scent glands on their feet.",
        "Their diet is low in nutrition, so they conserve energy by sleeping.",
        "Red pandas are endangered with fewer than 10,000 left.",
        "They have white faces with reddish-brown 'tear tracks'.",
        "Red pandas can rotate their ankles to climb down trees headfirst.",
        "They were discovered by Europeans before the giant panda."
    ]

    WHALE_FACTS = [
        "The blue whale is the largest animal ever known to exist.",
        "A blue whale's heart can weigh as much as a car.",
        "Whales are mammals, not fish, and breathe air through blowholes.",
        "Humpback whales sing complex songs that can last 20 minutes.",
        "Whales communicate across hundreds of miles in the ocean.",
        "A whale's spout is warm air condensing, not water from the ocean.",
        "Sperm whales have the largest brains of any animal.",
        "Gray whales migrate up to 12,000 miles round trip each year.",
        "Whales sleep by resting one half of their brain at a time.",
        "Orcas are actually the largest species of dolphin.",
        "Whales filter feed using baleen instead of teeth (most species).",
        "A blue whale's tongue can weigh as much as an elephant.",
        "Whales have a thick layer of blubber to stay warm.",
        "Newborn blue whales gain 200 pounds a day.",
        "Whales evolved from land-dwelling mammals about 50 million years ago.",
        "Beluga whales are sometimes called 'sea canaries' for their songs."
    ]

    KANGAROO_FACTS = [
        "Kangaroos cannot walk backwards.",
        "They are the only large animals that hop to move.",
        "A kangaroo's tail acts as a fifth leg for balance.",
        "Female kangaroos have a pouch called a marsupium.",
        "Baby kangaroos, called joeys, are born the size of a jellybean.",
        "Red kangaroos can hop at 35 mph and leap 25 feet.",
        "Kangaroos are marsupials native to Australia.",
        "A group of kangaroos is called a 'mob'.",
        "Kangaroos can survive long periods without drinking water.",
        "Male kangaroos box each other to compete for mates.",
        "Kangaroos have powerful hind legs and sharp claws.",
        "There are over 60 species of kangaroo and wallaby.",
        "A kangaroo can pause its pregnancy until conditions improve.",
        "Kangaroos mostly eat grass and are nocturnal grazers.",
        "Kangaroo meat is lean and high in protein.",
        "Joeys stay in the pouch for about 8 months."
    ]

    BUNNY_FACTS = [
        "Rabbits can purr when they are happy.",
        "A rabbit's teeth never stop growing.",
        "Rabbits have nearly 360-degree vision.",
        "A baby rabbit is called a kit or kitten.",
        "Rabbits communicate by thumping their hind legs.",
        "A group of rabbits is called a 'fluffle'.",
        "Rabbits can jump up to 3 feet high and 10 feet long.",
        "Rabbits are crepuscular, most active at dawn and dusk.",
        "A rabbit's nose can wiggle up to 20 times per second.",
        "Rabbits use their whiskers to sense their surroundings.",
        "Rabbits eat their own droppings to reabsorb nutrients.",
        "There are over 300 breeds of domestic rabbits.",
        "Rabbits have a blind spot directly in front of their nose.",
        "A rabbit's ears help regulate its body temperature.",
        "Rabbits can be litter-trained like cats.",
        "The world's largest rabbit weighed over 50 pounds."
    ]

    LION_FACTS = [
        "Lions are the only cats that live in social groups called prides.",
        "A lion's roar can be heard up to 5 miles away.",
        "Male lions' manes indicate health and testosterone levels.",
        "Lions can sleep up to 20 hours a day.",
        "Female lions do most of the hunting for the pride.",
        "A lion can run up to 50 mph in short bursts.",
        "Lions are found mainly in sub-Saharan Africa.",
        "A group of lions is called a pride; a group of cubs is a 'creche'.",
        "Lions have retractable claws for gripping prey.",
        "A lion's tongue is rough enough to peel skin from meat.",
        "Lion cubs are born with spots that fade as they grow.",
        "An adult male lion can weigh over 400 pounds.",
        "Lions can eat up to 40 pounds of meat in one meal.",
        "Lions communicate with roars, growls, and head rubs.",
        "White lions are a rare color mutation, not a separate species.",
        "Lions used to roam across Europe, Asia, and Africa."
    ]

    FROG_FACTS = [
        "Frogs absorb water through their skin, not by drinking.",
        "Some frogs can jump over 20 times their body length.",
        "A group of frogs is called an 'army'.",
        "Frogs have translucent eyelids called nictitating membranes.",
        "The golden poison dart frog has enough toxin to kill 10 humans.",
        "Frogs use their eyeballs to help swallow food.",
        "Some frogs can freeze solid and thaw back to life.",
        "A frog's call is made by passing air over vocal cords in a throat sac.",
        "Tadpoles breathe through gills before becoming frogs.",
        "The smallest frog is smaller than a coin; the largest eats birds.",
        "Frogs shed and eat their own skin.",
        "Many frogs have sticky tongues that snap out in milliseconds.",
        "Wood frogs can survive Arctic winters by freezing.",
        "Frogs have been around for 200 million years.",
        "A frog's ears are round spots behind its eyes.",
        "Some frogs are brightly colored to warn predators they are toxic."
    ]

    DUCK_FACTS = [
        "Ducks have waterproof feathers coated in oil from their tails.",
        "A duck's quack doesn't echo, or so the myth goes.",
        "Ducks can sleep with one eye open and half a brain awake.",
        "Male ducks are called drakes; females are hens; babies are ducklings.",
        "Ducks have three eyelids.",
        "Some ducks can fly at 60 mph during migration.",
        "A duck's foot has webbing to help it swim.",
        "Ducks have excellent vision and see in color.",
        "Mallards can live 5-10 years in the wild.",
        "Ducks are omnivores and eat plants, insects, and small fish.",
        "A duck's bill is sensitive and helps it find food underwater.",
        "Ducks preen to keep feathers clean and waterproof.",
        "Some ducks migrate thousands of miles each year.",
        "Ducks communicate with a range of quacks, whistles, and coos.",
        "A group of ducks on water is called a 'paddling'.",
        "Ducks have a special gland that makes them float higher."
    ]

    PENGUIN_FACTS = [
        "Penguins are birds that cannot fly but are expert swimmers.",
        "Emperor penguins can dive over 1,800 feet deep.",
        "Penguins are found mostly in the Southern Hemisphere.",
        "Male emperor penguins incubate the egg on their feet for 2 months.",
        "A group of penguins on land is called a 'waddle'.",
        "Penguins have a layer of fat and dense feathers to stay warm.",
        "The fastest swimming penguin reaches 22 mph.",
        "Penguins propose with a pebble to their mate.",
        "A penguin's black and white is camouflage from predators.",
        "Some penguins can hold their breath for 20 minutes.",
        "Gentoo penguins are the fastest underwater penguins.",
        "Penguins' wings evolved into flippers.",
        "Adelie penguins build nests from stones.",
        "Penguins can drink seawater thanks to special glands.",
        "The smallest penguin, the little blue, is about 16 inches tall.",
        "Penguins mate for life in many species."
    ]

    DOLPHIN_FACTS = [
        "Dolphins are highly intelligent marine mammals.",
        "They use echolocation to find food and navigate.",
        "Dolphins sleep with one half of their brain at a time.",
        "They communicate with clicks, whistles, and body language.",
        "A dolphin can swim up to 20 mph.",
        "Bottlenose dolphins live in groups called pods.",
        "Dolphins have been known to help injured members of their pod.",
        "A dolphin's blowhole is on top of its head for breathing.",
        "Newborn dolphins are called calves and can swim at birth.",
        "Dolphins can recognize themselves in mirrors.",
        "They have 80-100 teeth but swallow food whole.",
        "Dolphins have excellent hearing above and below water.",
        "Some dolphins use tools like sponges to protect their snouts.",
        "Orcas are the largest species of dolphin.",
        "Dolphins breathe consciously and must remember to surface.",
        "A dolphin's skin heals quickly from wounds."
    ]

    BEAR_FACTS = [
        "Bears are found on every continent except Antarctica and Australia.",
        "Polar bears have black skin under their white fur.",
        "A bear's sense of smell is about 7 times better than a bloodhound's.",
        "Bears can run up to 35 mph despite their size.",
        "Most bears are omnivores.",
        "Bears hibernate in winter to conserve energy.",
        "A panda is a bear that eats almost only bamboo.",
        "Grizzly bears can weigh up to 800 pounds.",
        "Bears have 42 teeth designed for omnivorous diets.",
        "Sun bears have the longest tongues of any bear species.",
        "Bears are mostly solitary animals.",
        "A bear's claws are non-retractable.",
        "Sloth bears love termites and suck them up loudly.",
        "Bears can stand on their hind legs to see farther.",
        "A bear's lifespan in the wild is 15-30 years.",
        "Bears communicate with sounds, scents, and body postures."
    ]

    AXOLOTL_FACTS = [
        "Axolotls are a type of salamander that never grows up.",
        "They keep their gills and live underwater their whole lives.",
        "Axolotls can regenerate lost limbs, spinal cord, and even parts of the brain.",
        "They are native only to lakes near Mexico City.",
        "Axolotls come in colors like pink, black, and gold.",
        "They are critically endangered in the wild.",
        "Axolotls can accept organs transplanted from other individuals.",
        "A baby axolotl is called a larva.",
        "They breathe through external gills that look like feathers.",
        "Axolotls eat worms, insects, and small fish.",
        "They can live 10-15 years in captivity.",
        "Axolotls are used heavily in scientific regeneration research.",
        "They rarely bite and are calm in captivity.",
        "Axolotls have a wide smile-like face.",
        "They can regenerate the same limb many times.",
        "Axolotls are popular as exotic pets but need clean cool water."
    ]

    CAPYBARA_FACTS = [
        "Capybaras are the largest rodents in the world.",
        "They are native to South America.",
        "Capybaras are semi-aquatic and love to swim.",
        "They have webbed feet for paddling.",
        "Capybaras are social and live in groups up to 30.",
        "Their closest relatives are guinea pigs.",
        "Capybaras can stay underwater for up to 5 minutes.",
        "They communicate with barks, whistles, and purrs.",
        "Capybaras eat grass and aquatic plants.",
        "They are surprisingly good around other animals and even cats.",
        "A capybara can weigh up to 140 pounds.",
        "They have a block-shaped head and small ears set back.",
        "Capybaras are hunted in some regions for meat.",
        "They can run as fast as a horse for short distances.",
        "Baby capybaras can walk within hours of birth.",
        "Their eyes, ears, and nostrils sit high on the head for swimming."
    ]

    TRIVIA = [
        ("What is the capital of France?", "Paris"),
        ("How many continents are there?", "7"),
        ("What is the largest planet in our solar system?", "Jupiter"),
        ("Who painted the Mona Lisa?", "Leonardo da Vinci"),
        ("What year did World War II end?", "1945"),
        ("What is the chemical symbol for gold?", "Au"),
        ("How many bones are in the adult human body?", "206"),
        ("What is the speed of light in km/s?", "299,792"),
        ("Who wrote 'Romeo and Juliet'?", "William Shakespeare"),
        ("What is the longest river in the world?", "The Nile"),
        ("How many elements are in the periodic table?", "118"),
        ("What is the smallest country in the world?", "Vatican City"),
        ("Who was the first person on the moon?", "Neil Armstrong"),
        ("What is the tallest mountain in the world?", "Mount Everest"),
        ("What language has the most native speakers?", "Mandarin Chinese"),
        ("How many hearts does an octopus have?", "3"),
        ("What year did the Titanic sink?", "1912"),
        ("What is the hardest natural substance?", "Diamond"),
        ("Who discovered penicillin?", "Alexander Fleming"),
        ("What is the largest ocean on Earth?", "Pacific Ocean"),
        ("How many stripes are on the US flag?", "13"),
        ("What is the boiling point of water in Celsius?", "100"),
        ("Who is known as the Father of Computers?", "Charles Babbage"),
        ("What is the national animal of Australia?", "Kangaroo"),
        ("How many teeth does an adult human have?", "32")
    ]

    JOKES = [
        "Why don't skeletons fight each other? They don't have the guts.",
        "What do you call a fish with no eyes? Fsh.",
        "Why did the cookie go to the hospital? Because it was feeling crummy.",
        "What do you call a bear with no teeth? A gummy bear.",
        "Why was the math book sad? It had too many problems.",
        "How do you catch a squirrel? Climb a tree and act like a nut.",
        "What's brown and sticky? A stick.",
        "Why can't you give Elsa a balloon? Because she'll let it go.",
        "What do you call a pig that does karate? A pork chop.",
        "Why did the tomato turn red? Because it saw the salad dressing.",
        "What do you call a snowman with a six-pack? An abdominal snowman.",
        "Why don't eggs tell jokes? They'd crack each other up.",
        "What's a computer's favorite snack? Microchips.",
        "How do you make a tissue dance? Put a little boogie in it.",
        "What do you call a fake noodle? An impasta.",
        "Why did the picture go to jail? Because it was framed.",
        "What's the best thing about Switzerland? I don't know, but the flag is a big plus.",
        "How many tickles does it take to make an octopus laugh? Ten-tickles.",
        "Why did the scarecrow win an award? He was outstanding in his field.",
        "What do you call a cow with two legs? Lean beef.",
        "Why don't scientists trust atoms? They make up everything.",
        "What's ET short for? Because he's got little legs.",
        "Why did the bicycle fall over? It was two tired.",
        "How does a penguin build its house? Igloos it together.",
        "What do you call a dog that can do magic? A Labracadabrador."
    ]

    CHUCK_NORRIS = [
        "Chuck Norris can divide by zero.",
        "Chuck Norris doesn't do pushups. He pushes the Earth down.",
        "Chuck Norris counted to infinity. Twice.",
        "When the Boogeyman goes to sleep, he checks his closet for Chuck Norris.",
        "Chuck Norris can hear sign language.",
        "Chuck Norris can slam a revolving door.",
        "Chuck Norris doesn't wear a watch. HE decides what time it is.",
        "Chuck Norris can win a game of Connect Four in three moves.",
        "Chuck Norris's tears cure cancer. Too bad he never cries.",
        "Death once had a near-Chuck-Norris experience.",
        "Chuck Norris can light a fire by rubbing two ice cubes together.",
        "Chuck Norris can do a wheelie on a unicycle.",
        "Chuck Norris can speak braille.",
        "Chuck Norris can strangle you with a cordless phone.",
        "Chuck Norris once kicked a horse in the chin. Its descendants are known as giraffes."
    ]

    RIDDLES = [
        ("What has keys but can't open locks?", "A piano"),
        ("What has a head and a tail but no body?", "A coin"),
        ("What gets wetter the more it dries?", "A towel"),
        ("What can travel around the world while staying in a corner?", "A stamp"),
        ("What has an eye but cannot see?", "A needle"),
        ("What has hands but can't clap?", "A clock"),
        ("What can you break without touching it?", "A promise"),
        ("What goes up but never comes down?", "Your age"),
        ("What is full of holes but still holds water?", "A sponge"),
        ("What can you catch but not throw?", "A cold"),
        ("What has a neck but no head?", "A bottle"),
        ("What has words but never speaks?", "A book"),
        ("What has legs but doesn't walk?", "A table"),
        ("What can fill a room but takes up no space?", "Light"),
        ("What disappears as soon as you say its name?", "Silence")
    ]

    QUOTES = [
        ("The only way to do great work is to love what you do.", "Steve Jobs"),
        ("In three words I can sum up everything about life: it goes on.", "Robert Frost"),
        ("Be yourself; everyone else is already taken.", "Oscar Wilde"),
        ("Two things are infinite: the universe and human stupidity.", "Albert Einstein"),
        ("Be the change that you wish to see in the world.", "Mahatma Gandhi"),
        ("Life is what happens when you're busy making other plans.", "John Lennon"),
        ("The purpose of our lives is to be happy.", "Dalai Lama"),
        ("Get busy living or get busy dying.", "Stephen King"),
        ("You only live once, but if you do it right, once is enough.", "Mae West"),
        ("Many of life's failures are people who did not realize how close they were to success when they gave up.", "Thomas Edison"),
        ("If you want to live a happy life, tie it to a goal, not to people or things.", "Albert Einstein"),
        ("Never let the fear of striking out keep you from playing the game.", "Babe Ruth"),
        ("Money and success don't change people; they merely amplify what is already there.", "Will Smith"),
        ("Not how long, but how well you have lived is the main thing.", "Seneca"),
        ("If life were predictable it would cease to be life, and be without flavor.", "Eleanor Roosevelt"),
        ("The unexamined life is not worth living.", "Socrates"),
        ("Turn your wounds into wisdom.", "Oprah Winfrey"),
        ("The way I see it, if you want the rainbow, you gotta put up with the rain.", "Dolly Parton"),
        ("Do all the good you can, for all the people you can, in all the ways you can, as long as you can.", "John Wesley"),
        ("Don't settle for what life gives you; make life better and build something.", "Ashton Kutcher"),
        ("Everything negative – pressure, challenges – is all an opportunity for me to rise.", "Kobe Bryant"),
        ("I like criticism. It makes you strong.", "LeBron James"),
        ("You never really learn much from hearing yourself speak.", "George Clooney"),
        ("Life imposes things on you that you can't control, but you still have the choice of how you're going to live through this.", "Celine Dion"),
        ("Life is never easy. There is work to be done and obligations to be met – obligations to truth, to justice, and to liberty.", "John F. Kennedy")
    ]

    PICKUP_LINES = [
        "Are you a magician? Because whenever I look at you, everyone else disappears.",
        "Do you have a map? I keep getting lost in your eyes.",
        "Are you made of copper and tellurium? Because you're Cu-Te.",
        "If you were a vegetable, you'd be a cute-cumber.",
        "Do you have a Band-Aid? I scraped my knee falling for you.",
        "Are you a parking ticket? Because you've got FINE written all over you.",
        "Is your name Google? Because you have everything I'm searching for.",
        "Are you a time traveler? Because I see you in my future.",
        "Do you believe in love at first sight, or should I walk by again?",
        "Is your dad a boxer? Because you're a knockout.",
        "Are you a camera? Because every time I look at you, I smile.",
        "Do you have a sunburn, or are you always this hot?",
        "Are you a bank loan? Because you have my interest.",
        "If you were a fruit, you'd be a fine-apple.",
        "Are you a Wi-Fi signal? Because I'm feeling a connection.",
        "I must be a snowflake, because I've fallen for you.",
        "Are you a cat? Because I'm feline a connection.",
        "Is your name Chapstick? Because you're da balm.",
        "Do you like Star Wars? Because Yoda only one for me.",
        "Are you a 45-degree angle? Because you're acute-y.",
        "I'm not a photographer, but I can picture us together.",
        "Is your name Ariel? Because we were mermaid for each other.",
        "Are you a beaver? Because daaaaam.",
        "If I were a stop light, I'd turn red every time you passed by, just so I could stare at you a bit longer.",
        "Are you a campfire? Because you're hot and I want s'more."
    ]

    COMMIT_MESSAGES = [
        "fixed bug that wasn't there",
        "works on my machine",
        "quick fix, will refactor later (never)",
        "I don't know what I'm doing",
        "fixed merge conflict by deleting everything",
        "added magic numbers",
        "removed unneeded code... broke everything",
        "TODO: write commit message",
        "one more commit before bed",
        "it compiles, ship it",
        "fixed typo",
        "another fix",
        "test commit please ignore",
        "this should work maybe",
        "I have no idea what changed",
        "deleted code that was only commented out anyway",
        "my boss told me to commit",
        "Friday afternoon commit",
        "fixed the fix that broke the fix",
        "minor changes (rewrote entire codebase)",
        "added swear words to comments",
        "praying this doesn't break production",
        "definitely not a pyramid scheme of hacks",
        "I'll explain this commit message in the next commit",
        "removed all bugs"
    ]

    SHOWER_THOUGHTS = [
        "If you fall and nobody is around to hear it, you still made a sound. You just didn't hear it either.",
        "Hospitals are just buildings where people collectively agree to go when they're dying.",
        "The person who proofreads the dictionary must be the most bored person alive.",
        "You've never seen your own face, only pictures and reflections.",
        "A clear conscience is usually the sign of a bad memory.",
        "If you think about it, 'Do Not Disturb' is the most disturbing sign on a door.",
        "When you're a kid, you don't realize you're also watching your parents grow up.",
        "The word 'ambiguous' is only ambiguous if you don't know what it means.",
        "Nothing is ever on fire. Fire is on things.",
        "Your stomach thinks all potatoes are mashed.",
        "You can't say 'bubbles' in an angry way.",
        "The acronym 'TBD' is a perfect example of itself.",
        "Saying 'no offense' doesn't make it less offensive, just like saying 'no homo' doesn't make it less gay.",
        "Aliens might be observing us and thinking Earth is a reality TV show.",
        "The word 'listen' has the same letters as 'silent'.",
        "Your future self is watching you right now through memories.",
        "If I drop my phone on my face in bed, my phone is technically assaulting me.",
        "The letter 'W' is called double-U even though it's clearly a double-V.",
        "Your nose is always in your field of vision but your brain ignores it.",
        "When you drink alcohol, you're essentially borrowing happiness from tomorrow.",
        "Every book is a children's book if the kid can read.",
        "You are someone else's 'someone else'.",
        "The oldest person in the world was once the youngest person in the world.",
        "Statistically, you're more likely to be killed by a cow than a shark.",
        "Goosebumps are useless now, but they used to make our ancestors look bigger to predators."
    ]

    EVIL_INSULTS = [
        "You are the human equivalent of a participation trophy.",
        "I'd agree with you, but then we'd both be wrong.",
        "You bring everyone so much joy when you leave the room.",
        "I'm not saying I hate you, but if you were on fire and I had water, I'd drink it.",
        "You have the right to remain silent because whatever you say is probably stupid.",
        "You're not the dumbest person alive, but you'd better hope they don't die.",
        "I've seen salads more intimidating than you.",
        "You're the reason the gene pool needs a lifeguard.",
        "Somewhere out there, a tree is tirelessly producing oxygen so you can breathe. I think you owe it an apology.",
        "You're like a gray sky. You make everything seem dull.",
        "If I had a dollar for every time you said something smart, I'd be broke.",
        "You're not stupid. You just have bad luck thinking.",
        "I'd explain it to you, but I left my crayons at home.",
        "You're proof that evolution can go in reverse.",
        "I'd tell you to go to hell, but I don't want to see you again.",
        "If ignorance is bliss, you must be the happiest person on Earth.",
        "You're like a software update. I see you, but I ignore you.",
        "Your secrets are safe with me. I never even listen when you tell me them.",
        "You have an entire lifetime to be an idiot. Why not take today off?",
        "I thought of you today. It reminded me to take out the trash."
    ]

    TRUTH_QUESTIONS = [
        "What's the last lie you told?",
        "What's the most embarrassing thing you've ever done?",
        "Have you ever cheated on a test?",
        "What's the worst thing you've ever said to someone?",
        "What's a secret you've never told anyone?",
        "Have you ever stolen something?",
        "What's your biggest insecurity?",
        "Who was your first crush?",
        "What's the most trouble you've been in?",
        "Have you ever pretended to like a gift?",
        "What's the worst date you've ever been on?",
        "Have you ever ghosted someone?",
        "What's something you're glad your parents don't know?",
        "Have you ever faked being sick?",
        "What's your guilty pleasure?",
        "What's the meanest thing you've ever done?",
        "Have you ever looked through someone's phone without permission?",
        "What's the most childish thing you still do?",
        "Have you ever said 'I love you' without meaning it?",
        "What's the worst rumor you've spread?",
        "Have you ever broken the law?",
        "What's the most awkward situation you've been in?",
        "Have you ever blamed someone else for something you did?",
        "What's something you pretend to understand but don't?",
        "Have you ever eavesdropped on a private conversation?"
    ]

    DARE_CHALLENGES = [
        "Do an impression of another person in the server until someone guesses who it is.",
        "Post the last selfie you took.",
        "Let someone else change your nickname for 24 hours.",
        "Speak only in rhymes for the next 10 minutes.",
        "Send a voice message singing the chorus of your favorite song.",
        "Post the oldest photo on your phone.",
        "Use only emojis to communicate for the next 5 minutes.",
        "Tell a joke so bad it's funny.",
        "Share your most recent Google search.",
        "Do a dramatic reading of the last DM you received.",
        "Post your screen time for the past week.",
        "Let someone pick your profile picture for an hour.",
        "Speak in third person for 10 minutes.",
        "Share the last song you listened to.",
        "Write a haiku about the person above you.",
        "Post a picture of your fridge/pantry.",
        "Try to lick your elbow and report back.",
        "Say the alphabet backwards as fast as you can.",
        "Describe everyone in the server using one word each.",
        "Share an unpopular opinion you hold.",
        "Draw a self-portrait in MS Paint and share it.",
        "Type with your eyes closed for 5 sentences.",
        "Recreate a famous movie scene using only text.",
        "Share the last thing you copied to your clipboard.",
        "Speak in a fake accent for the next 15 minutes."
    ]

    NEVER_HAVE_I_EVER = [
        "Never have I ever faked a phone call to get out of something.",
        "Never have I ever stalked someone's social media for more than an hour.",
        "Never have I ever lied on a resume.",
        "Never have I ever eaten food that fell on the floor.",
        "Never have I ever pretended to know a stranger.",
        "Never have I ever re-gifted a present.",
        "Never have I ever fallen asleep in class or a meeting.",
        "Never have I ever used a fake ID.",
        "Never have I ever ghosted someone after a date.",
        "Never have I ever sent a text to the wrong person.",
        "Never have I ever lied about my age.",
        "Never have I ever Googled my own name.",
        "Never have I ever cried during a movie.",
        "Never have I ever eaten an entire pizza by myself.",
        "Never have I ever talked to myself in the mirror.",
        "Never have I ever pretended to like a food I actually hate.",
        "Never have I ever screenshotted a conversation.",
        "Never have I ever stayed up all night.",
        "Never have I ever laughed so hard I cried.",
        "Never have I ever walked into a glass door.",
        "Never have I ever pretended to be on my phone to avoid someone.",
        "Never have I ever forgotten someone's name immediately after meeting them.",
        "Never have I ever fallen for a prank.",
        "Never have I ever sang in the shower.",
        "Never have I ever talked to my pet like it's a person."
    ]

    PARANOIA_QUESTIONS = [
        "Who in this server would be most likely to survive a zombie apocalypse?",
        "If the police showed up right now, who would be the most nervous?",
        "Who here is most likely to have a secret double life?",
        "If everyone's DMs were leaked, whose would be the most scandalous?",
        "Who is most likely to be a serial killer?",
        "Who would sell everyone out for a million dollars?",
        "Who has the most skeletons in their closet?",
        "If one person here was an alien, who would it be?",
        "Who would be the worst person to be stranded on an island with?",
        "Who is most likely to be an undercover cop?",
        "Who probably Googled themselves before joining this server?",
        "Whose search history would be the most incriminating?",
        "Who would be the first to die in a horror movie?",
        "Who is most likely to talk to themselves when alone?",
        "Who here is probably using a fake profile picture?",
        "If everyone here was a suspect in a crime, who'd be convicted first?",
        "Who is most likely reading this and feeling personally attacked?",
        "Who would sacrifice everyone else to save themselves?",
        "Who here is definitely a catfish?",
        "Who talks the most in DMs but stays quiet in public?",
        "Who would accidentally reveal a secret in their sleep?",
        "Who screenshots conversations the most?",
        "Who has the most burner accounts?",
        "Who probably talks to their plants?",
        "Who here is definitely going to be famous one day?"
    ]

    RICK_ROLL_LYRICS = [
        "We're no strangers to love",
        "You know the rules and so do I",
        "A full commitment's what I'm thinking of",
        "You wouldn't get this from any other guy",
        "I just wanna tell you how I'm feeling",
        "Gotta make you understand",
        "Never gonna give you up",
        "Never gonna let you down",
        "Never gonna run around and desert you",
        "Never gonna make you cry",
        "Never gonna say goodbye",
        "Never gonna tell a lie and hurt you",
        "We've known each other for so long",
        "Your heart's been aching, but you're too shy to say it",
        "Inside, we both know what's been going on",
        "We know the game and we're gonna play it",
        "And if you ask me how I'm feeling",
        "Don't tell me you're too blind to see",
        "Never gonna give you up",
        "Never gonna let you down",
        "Never gonna run around and desert you",
        "Never gonna make you cry",
        "Never gonna say goodbye",
        "Never gonna tell a lie and hurt you",
        "Never gonna give you up",
        "Never gonna let you down",
        "Never gonna run around and desert you",
        "Never gonna make you cry",
        "Never gonna say goodbye",
        "Never gonna tell a lie and hurt you"
    ]

    NOT_FUNNY_COPYPASTA = """I just downvoted your comment.
# FAQ
## What does this mean?
The amount of karma (points) on your comment and Reddit account has decreased by one.
## Why did you do this?
There are several reasons I may deem a comment to be unworthy of positive or neutral karma. These include, but are not limited to:
* Rudeness towards other Redditors,
* Spreading incorrect information,
* Sarcasm not correctly flagged with a /s.
## Am I banned from the Reddit?
No - not yet. But you should refrain from making comments like this in the future. Otherwise I will be forced to issue an additional downvote, which may put your commenting and posting privileges in jeopardy.
## I don't believe my comment deserved a downvote. Can you un-downvote it?
Sure, mistakes happen. But only in exceedingly rare circumstances will I undo a downvote. If you would like to issue an appeal, shoot me a private message explaining what I got wrong. I tend to respond to Reddit PMs within several minutes. Do note, however, that over 99.9% of downvote appeals are rejected, and yours is likely no exception.
## How can I prevent this from happening in the future?
Accept the downvote and move on. But learn from this mistake: your behavior will not be tolerated on Reddit.com. I will continue to issue downvotes until you improve your conduct. Remember: Reddit is privilege, not a right."""

    RANDOM_QUESTIONS = [
        "If you could live in any fictional universe, which one would you choose?",
        "What's a food you hated as a kid but love now?",
        "If animals could talk, which species would be the most annoying?",
        "What's the weirdest compliment you've ever received?",
        "If you were a ghost, who would you haunt?",
        "What's the most useless superpower you can think of?",
        "If your life was a movie, what genre would it be?",
        "What's something that's illegal but shouldn't be?",
        "What's something that's legal but shouldn't be?",
        "If you could delete one thing from existence, what would it be?",
        "What's the most overrated food?",
        "What's a smell that brings back strong memories for you?",
        "If you could only wear one color for the rest of your life, what color?",
        "What's the weirdest thing you believed as a child?",
        "If you could swap voices with any celebrity, whose would you take?",
        "What's the worst piece of advice you've ever received?",
        "What's a word you always misspell?",
        "If you had a warning label, what would it say?",
        "What's the most awkward thing that happens on a regular basis?",
        "If your pet could talk, what's the first thing it would say?",
        "What's something you find attractive that others might find weird?",
        "If you could master any skill overnight, what would it be?",
        "What's a conspiracy theory you secretly believe?",
        "What's the most 'dad' thing you've ever done?",
        "If you could be the best in the world at something useless, what would it be?"
    ]

    BORED_ACTIVITIES = [
        "Learn a new card trick.",
        "Start a Wikipedia rabbit hole from a random article.",
        "Rearrange your furniture.",
        "Write a letter to your future self.",
        "Learn the alphabet in sign language.",
        "Bake cookies from scratch.",
        "Create a playlist for a specific mood.",
        "Do a 10-minute meditation session.",
        "Draw a self-portrait without looking at the paper.",
        "Organize your digital files and folders.",
        "Watch a documentary about something you know nothing about.",
        "Try origami with whatever paper you have.",
        "Write a short story in exactly 100 words.",
        "Learn how to tie five different knots.",
        "Plan a dream vacation itinerary.",
        "Memorize a poem.",
        "Do bodyweight exercises until you can't anymore.",
        "Photograph 10 interesting things within walking distance.",
        "Learn to count to 10 in three new languages.",
        "Create a bucket list.",
        "Build something with items you already own.",
        "Research your family tree online.",
        "Clean one thing you've been avoiding.",
        "Try to learn the first few measures of a song on an instrument or virtual piano."
    ]

    STARTUP_IDEAS = [
        "Uber, but for finding someone to assemble your IKEA furniture.",
        "A subscription box that sends you a new type of hot sauce each month, but they get progressively hotter until you question your life choices.",
        "Tinder, but for matching people based on their Netflix watch history.",
        "An app that tells you which public bathrooms are the cleanest near you.",
        "A service that forwards your spam emails to someone you hate.",
        "Airbnb, but for parking spots in crowded cities.",
        "A smart mirror that compliments you every morning.",
        "A meal delivery service that only delivers food you've never tried before.",
        "A social network where you can only post once per day.",
        "An alarm clock that donates money to a charity you hate every time you snooze.",
        "A dating app where you match based on your most controversial opinions.",
        "A platform where people can hire someone to attend awkward social events for them.",
        "Netflix, but for podcasts with video.",
        "A service that sends glitter bombs to anyone you want, no questions asked.",
        "An app that translates what your cat is probably thinking based on their meows.",
        "A subscription service for left socks only.",
        "A website that rates the spiciness of different types of toothpaste.",
        "A service that sends a professional photographer to take candid photos of you in public so you look cool on social media.",
        "Virtual reality, but for trying on clothes before buying online.",
        "A platform that connects people who want to argue about the same things."
    ]

    WEIRD_WORDS = [
        "Bamboozle", "Flabbergast", "Lollygag", "Malarkey", "Hullabaloo",
        "Rigmarole", "Skedaddle", "Higgledy-piggledy", "Hornswoggle", "Snollygoster",
        "Gobbledygook", "Flummox", "Nincompoop", "Poppycock", "Shenanigans",
        "Kerfuffle", "Brouhaha", "Doohickey", "Thingamajig", "Whatsit",
        "Whirligig", "Dingleberry", "Fiddlesticks", "Bupkis", "Collywobbles",
        "Gubbins", "Hoosegow", "Lickety-split", "Mumbo-jumbo", "Razzmatazz"
    ]

    RANDOM_WORDS = [
        "Serendipity", "Ephemeral", "Quintessential", "Petrichor", "Mellifluous",
        "Ethereal", "Ineffable", "Solitude", "Aurora", "Phantasm",
        "Labyrinth", "Cascade", "Whisper", "Velvet", "Crystalline",
        "Enigma", "Symphony", "Oblivion", "Reverie", "Paradox",
        "Tranquility", "Luminescence", "Evanescent", "Halcyon", "Incandescent",
        "Opulent", "Epiphany", "Mirage", "Zenith", "Hiraeth"
    ]

    FML_QUOTES = [
        "Today, I found out my girlfriend of 3 years has been cheating on me with my twin brother. They're getting married next month. FML",
        "Today, my boss caught me sleeping at my desk. I was dreaming about work. FML",
        "Today, I realized the 'free trial' I forgot to cancel a year ago has charged me $30 every month. FML",
        "Today, I waved back at someone who was waving at the person behind me. FML",
        "Today, I spent 20 minutes rehearsing what I'd say when I answered the phone, then hung up without speaking. FML",
        "Today, I slipped on a banana peel. In front of the whole cafeteria. Yes, a banana peel. FML",
        "Today, I texted my crush 'I love you' and accidentally sent it to my mom. FML",
        "Today, I locked myself out of my car while it was still running. FML",
        "Today, I tried to be healthy and ate a salad. A worm was in it. FML",
        "Today, I stayed up all night to finish a project. The teacher extended the deadline. FML",
        "Today, I got rejected from a job because I was 'overqualified'. As a barista. FML",
        "Today, I sneezed so hard I peed a little and my dog judged me. FML",
        "Today, I called my teacher 'mom' in front of the whole class. FML",
        "Today, I bought concert tickets for a show that was last week. FML",
        "Today, I tried to flirt by spilling my drink 'on purpose'. It was on my crush's laptop. FML",
        "Today, I discovered my 'best friend' used my name as their WiFi password out of spite. FML",
        "Today, I practiced my signature for when I'm famous. I'm a cashier. FML",
        "Today, I walked into a meeting with toilet paper stuck to my shoe. FML",
        "Today, my little brother told my crush I have a shrine to them. I don't. Mostly. FML",
        "Today, I spent an hour looking for my phone in the dark. The flashlight was on. FML",
        "Today, I proposed a group selfie and everyone else had already left. FML",
        "Today, I accidentally liked my ex's photo from 3 years ago. FML",
        "Today, I celebrated Friday on a Wednesday. FML",
        "Today, I got a promotion and a pay cut in the same meeting. FML",
        "Today, I opened a bag of chips and it exploded all over my black shirt. FML"
    ]

    LUCIFER_QUOTES = [
        "I don't like to lose. And I really don't like to be lied to. So if you're gonna do either, you better be worth it.",
        "You know, people always say the devil's in the details. I just think details are what make life interesting.",
        "Everyone has a weakness, Detective. Even you.",
        "I'm the devil, but I can still appreciate good music.",
        "You can't run from who you are. Trust me, I've tried.",
        "Pride is a funny thing. It comes before the fall, but it also builds empires.",
        "I don't make deals, Detective. I make exceptions.",
        "Humans are fascinating. You destroy the things you claim to love.",
        "Hell isn't a place, Detective. It's a choice.",
        "You know what I've learned? People never change. They just get better at hiding it.",
        "I'm not the villain of your story. I'm just the part you don't understand.",
        "Love is a weakness. But it's the only one worth having.",
        "Everyone sells something. The question is what, and to whom.",
        "I've been many things, Detective. Patient isn't usually one of them.",
        "The truth is overrated. It's the lies we tell ourselves that keep us going.",
        "You can't save everyone. Believe me, I've tried.",
        "I don't do apologies. They're a human invention for people too weak to own their mistakes.",
        "Power isn't about being feared. It's about being necessary.",
        "I've read every book in every library. Humans still surprise me. Sadly.",
        "You know what hell really is? Boredom. Eternal, mind-numbing boredom.",
        "I gave humans free will. Look how that turned out.",
        "The best lies are the ones we tell ourselves.",
        "I don't punish people, Detective. They do that to themselves just fine.",
        "Even the devil gets lonely sometimes.",
        "You want to know the secret to immortality? Don't die. Harder than it sounds."
    ]

    STRANGER_THINGS_QUOTES = [
        "Friends don't lie.",
        "We never would have upset you if we didn't think you were our friend.",
        "Mouth breather.",
        "You're going to be home by 8:00. You're going to do your homework. You're going to do the dishes.",
        "I am on a busy street. There's a little kid on a tricycle. He's wearing a red shirt.",
        "It's not my fault I don't know what's going on. I just got here.",
        "Why are you keeping this curiosity door locked?",
        "She's our friend, and she's crazy!",
        "I just want things to go back to the way they were. Before all of this strange stuff started happening.",
        "We're not gonna tell anyone about this place, okay? This is our spot.",
        "You shouldn't like things because people tell you you're supposed to.",
        "I'm not gonna celebrate my birthday because birthdays are bogus.",
        "The truth is, I really like this. Being with you guys.",
        "Running away? That's not something friends do.",
        "I may be a stupid kid, but I know bullies when I see them.",
        "It's the '80s, y'know. We're supposed to be having fun.",
        "I'm listening to the Clash. Do you like the Clash?",
        "We did it! We saved the world from the upside down!",
        "Sometimes, people don't really say what they're really thinking.",
        "You act like you're all alone, but you've got friends right here.",
        "The walking dead girl, she's our friend.",
        "I can't believe you made me do that.",
        "I'm not crazy. I swear I saw something.",
        "Eleven? Is that you?",
        "You're headed the wrong way, kid. Turn around."
    ]

    # Default unicode emojis to mix with custom guild emojis
    DEFAULT_EMOJIS = [
        "😀", "😂", "🥰", "😎", "🤔", "😭", "🔥", "💀", "👀", "🎉",
        "💯", "🍕", "🌟", "🌈", "⚡", "🌸", "🍀", "🐱", "🐶", "🦄",
        "👑", "💎", "🍔", "🚀", "🌊", "🍉", "🎮", "🎵", "❤️", "✨"
    ]

    # Social command fallback GIFs (one per action; nekos API tried first)
    SOCIAL_FALLBACK = {
        "hug": [
            "https://media.tenor.com/hug1.gif",
            "https://media.tenor.com/hug2.gif",
            "https://media.tenor.com/hug3.gif",
            "https://media.tenor.com/hug4.gif",
            "https://media.tenor.com/hug5.gif",
        ],
        "kiss": [
            "https://media.tenor.com/kiss1.gif",
            "https://media.tenor.com/kiss2.gif",
            "https://media.tenor.com/kiss3.gif",
            "https://media.tenor.com/kiss4.gif",
            "https://media.tenor.com/kiss5.gif",
        ],
        "slap": [
            "https://media.tenor.com/slap1.gif",
            "https://media.tenor.com/slap2.gif",
            "https://media.tenor.com/slap3.gif",
            "https://media.tenor.com/slap4.gif",
            "https://media.tenor.com/slap5.gif",
        ],
        "cuddle": [
            "https://media.tenor.com/cuddle1.gif",
            "https://media.tenor.com/cuddle2.gif",
            "https://media.tenor.com/cuddle3.gif",
            "https://media.tenor.com/cuddle4.gif",
            "https://media.tenor.com/cuddle5.gif",
        ],
        "pat": [
            "https://media.tenor.com/pat1.gif",
            "https://media.tenor.com/pat2.gif",
            "https://media.tenor.com/pat3.gif",
            "https://media.tenor.com/pat4.gif",
            "https://media.tenor.com/pat5.gif",
        ],
        "feed": [
            "https://media.tenor.com/feed1.gif",
            "https://media.tenor.com/feed2.gif",
            "https://media.tenor.com/feed3.gif",
            "https://media.tenor.com/feed4.gif",
            "https://media.tenor.com/feed5.gif",
        ],
        "wink": [
            "https://media.tenor.com/wink1.gif",
            "https://media.tenor.com/wink2.gif",
            "https://media.tenor.com/wink3.gif",
            "https://media.tenor.com/wink4.gif",
            "https://media.tenor.com/wink5.gif",
        ],
    }

    # Periodic table: (number, name, symbol, mass, category)
    ELEMENT_DATA = [
        (1, "Hydrogen", "H", 1.008, "nonmetal"),
        (2, "Helium", "He", 4.0026, "noble gas"),
        (3, "Lithium", "Li", 6.94, "alkali metal"),
        (4, "Beryllium", "Be", 9.0122, "alkaline earth metal"),
        (5, "Boron", "B", 10.81, "metalloid"),
        (6, "Carbon", "C", 12.011, "nonmetal"),
        (7, "Nitrogen", "N", 14.007, "nonmetal"),
        (8, "Oxygen", "O", 15.999, "nonmetal"),
        (9, "Fluorine", "F", 18.998, "halogen"),
        (10, "Neon", "Ne", 20.180, "noble gas"),
        (11, "Sodium", "Na", 22.990, "alkali metal"),
        (12, "Magnesium", "Mg", 24.305, "alkaline earth metal"),
        (13, "Aluminum", "Al", 26.982, "post-transition metal"),
        (14, "Silicon", "Si", 28.085, "metalloid"),
        (15, "Phosphorus", "P", 30.974, "nonmetal"),
        (16, "Sulfur", "S", 32.06, "nonmetal"),
        (17, "Chlorine", "Cl", 35.45, "halogen"),
        (18, "Argon", "Ar", 39.948, "noble gas"),
        (19, "Potassium", "K", 39.098, "alkali metal"),
        (20, "Calcium", "Ca", 40.078, "alkaline earth metal"),
        (21, "Scandium", "Sc", 44.956, "transition metal"),
        (22, "Titanium", "Ti", 47.867, "transition metal"),
        (23, "Vanadium", "V", 50.942, "transition metal"),
        (24, "Chromium", "Cr", 51.996, "transition metal"),
        (25, "Manganese", "Mn", 54.938, "transition metal"),
        (26, "Iron", "Fe", 55.845, "transition metal"),
        (27, "Cobalt", "Co", 58.933, "transition metal"),
        (28, "Nickel", "Ni", 58.693, "transition metal"),
        (29, "Copper", "Cu", 63.546, "transition metal"),
        (30, "Zinc", "Zn", 65.38, "transition metal"),
        (31, "Gallium", "Ga", 69.723, "post-transition metal"),
        (32, "Germanium", "Ge", 72.630, "metalloid"),
        (33, "Arsenic", "As", 74.922, "metalloid"),
        (34, "Selenium", "Se", 78.971, "nonmetal"),
        (35, "Bromine", "Br", 79.904, "halogen"),
        (36, "Krypton", "Kr", 83.798, "noble gas"),
        (37, "Rubidium", "Rb", 85.468, "alkali metal"),
        (38, "Strontium", "Sr", 87.62, "alkaline earth metal"),
        (39, "Yttrium", "Y", 88.906, "transition metal"),
        (40, "Zirconium", "Zr", 91.224, "transition metal"),
        (41, "Niobium", "Nb", 92.906, "transition metal"),
        (42, "Molybdenum", "Mo", 95.95, "transition metal"),
        (43, "Technetium", "Tc", 98.0, "transition metal"),
        (44, "Ruthenium", "Ru", 101.07, "transition metal"),
        (45, "Rhodium", "Rh", 102.91, "transition metal"),
        (46, "Palladium", "Pd", 106.42, "transition metal"),
        (47, "Silver", "Ag", 107.87, "transition metal"),
        (48, "Cadmium", "Cd", 112.41, "transition metal"),
        (49, "Indium", "In", 114.82, "post-transition metal"),
        (50, "Tin", "Sn", 118.71, "post-transition metal"),
        (51, "Antimony", "Sb", 121.76, "metalloid"),
        (52, "Tellurium", "Te", 127.60, "metalloid"),
        (53, "Iodine", "I", 126.90, "halogen"),
        (54, "Xenon", "Xe", 131.29, "noble gas"),
        (55, "Cesium", "Cs", 132.91, "alkali metal"),
        (56, "Barium", "Ba", 137.33, "alkaline earth metal"),
        (57, "Lanthanum", "La", 138.91, "lanthanide"),
        (58, "Cerium", "Ce", 140.12, "lanthanide"),
        (59, "Praseodymium", "Pr", 140.91, "lanthanide"),
        (60, "Neodymium", "Nd", 144.24, "lanthanide"),
        (61, "Promethium", "Pm", 145.0, "lanthanide"),
        (62, "Samarium", "Sm", 150.36, "lanthanide"),
        (63, "Europium", "Eu", 151.96, "lanthanide"),
        (64, "Gadolinium", "Gd", 157.25, "lanthanide"),
        (65, "Terbium", "Tb", 158.93, "lanthanide"),
        (66, "Dysprosium", "Dy", 162.50, "lanthanide"),
        (67, "Holmium", "Ho", 164.93, "lanthanide"),
        (68, "Erbium", "Er", 167.26, "lanthanide"),
        (69, "Thulium", "Tm", 168.93, "lanthanide"),
        (70, "Ytterbium", "Yb", 173.05, "lanthanide"),
        (71, "Lutetium", "Lu", 174.97, "lanthanide"),
        (72, "Hafnium", "Hf", 178.49, "transition metal"),
        (73, "Tantalum", "Ta", 180.95, "transition metal"),
        (74, "Tungsten", "W", 183.84, "transition metal"),
        (75, "Rhenium", "Re", 186.21, "transition metal"),
        (76, "Osmium", "Os", 190.23, "transition metal"),
        (77, "Iridium", "Ir", 192.22, "transition metal"),
        (78, "Platinum", "Pt", 195.08, "transition metal"),
        (79, "Gold", "Au", 196.97, "transition metal"),
        (80, "Mercury", "Hg", 200.59, "transition metal"),
        (81, "Thallium", "Tl", 204.38, "post-transition metal"),
        (82, "Lead", "Pb", 207.2, "post-transition metal"),
        (83, "Bismuth", "Bi", 208.98, "post-transition metal"),
        (84, "Polonium", "Po", 209.0, "post-transition metal"),
        (85, "Astatine", "At", 210.0, "halogen"),
        (86, "Radon", "Rn", 222.0, "noble gas"),
        (87, "Francium", "Fr", 223.0, "alkali metal"),
        (88, "Radium", "Ra", 226.0, "alkaline earth metal"),
        (89, "Actinium", "Ac", 227.0, "actinide"),
        (90, "Thorium", "Th", 232.04, "actinide"),
        (91, "Protactinium", "Pa", 231.04, "actinide"),
        (92, "Uranium", "U", 238.03, "actinide"),
        (93, "Neptunium", "Np", 237.0, "actinide"),
        (94, "Plutonium", "Pu", 244.0, "actinide"),
        (95, "Americium", "Am", 243.0, "actinide"),
        (96, "Curium", "Cm", 247.0, "actinide"),
        (97, "Berkelium", "Bk", 247.0, "actinide"),
        (98, "Californium", "Cf", 251.0, "actinide"),
        (99, "Einsteinium", "Es", 252.0, "actinide"),
        (100, "Fermium", "Fm", 257.0, "actinide"),
        (101, "Mendelevium", "Md", 258.0, "actinide"),
        (102, "Nobelium", "No", 259.0, "actinide"),
        (103, "Lawrencium", "Lr", 266.0, "actinide"),
        (104, "Rutherfordium", "Rf", 267.0, "transition metal"),
        (105, "Dubnium", "Db", 268.0, "transition metal"),
        (106, "Seaborgium", "Sg", 269.0, "transition metal"),
        (107, "Bohrium", "Bh", 270.0, "transition metal"),
        (108, "Hassium", "Hs", 269.0, "transition metal"),
        (109, "Meitnerium", "Mt", 278.0, "unknown"),
        (110, "Darmstadtium", "Ds", 281.0, "unknown"),
        (111, "Roentgenium", "Rg", 282.0, "unknown"),
        (112, "Copernicium", "Cn", 285.0, "transition metal"),
        (113, "Nihonium", "Nh", 286.0, "post-transition metal"),
        (114, "Flerovium", "Fl", 289.0, "post-transition metal"),
        (115, "Moscovium", "Mc", 290.0, "post-transition metal"),
        (116, "Livermorium", "Lv", 293.0, "post-transition metal"),
        (117, "Tennessine", "Ts", 294.0, "halogen"),
        (118, "Oganesson", "Og", 294.0, "noble gas"),
    ]

    def _element_lookup(self, query: str):
        q = query.strip().lower()
        for number, name, symbol, mass, category in self.ELEMENT_DATA:
            if symbol.lower() == q or name.lower() == q:
                return {
                    "number": number,
                    "name": name,
                    "symbol": symbol,
                    "mass": mass,
                    "category": category,
                }
        return None

    # ------------------------------------------------------------------ #
    # Cog lifecycle
    # ------------------------------------------------------------------ #
    def cog_unload(self):
        if self.session and not self.session.closed:
            asyncio.create_task(self.session.close())

    # ------------------------------------------------------------------ #
    # 1. eightball
    # ------------------------------------------------------------------ #
    @commands.command(name="eightball")
    async def eightball(self, ctx, *, question: str):
        await self._delete_invoke(ctx)
        answer = random.choice(self.EIGHTBALL_RESPONSES)
        await ctx.send(f"🎱 **Question:** {question}\n**Answer:** {answer}")

    # ------------------------------------------------------------------ #
    # 2-6. seeded percentage commands
    # ------------------------------------------------------------------ #
    @commands.command(name="howgay")
    async def howgay(self, ctx, *, user: str = None):
        await self._delete_invoke(ctx)
        target = await self._resolve_user(ctx, user) or ctx.author
        random.seed(int(target.id))
        percent = random.randint(0, 100)
        random.seed()
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
        await ctx.send(f"🏳️‍🌈 {target.display_name} is {percent}% gay.\n`[{bar}] {percent}%`")

    @commands.command(name="howsimp")
    async def howsimp(self, ctx, *, user: str = None):
        await self._delete_invoke(ctx)
        target = await self._resolve_user(ctx, user) or ctx.author
        random.seed(int(target.id))
        percent = random.randint(0, 100)
        random.seed()
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
        await ctx.send(f"🍑 {target.display_name} is {percent}% simp.\n`[{bar}] {percent}%`")

    @commands.command(name="penis")
    async def penis(self, ctx, *, user: str = None):
        await self._delete_invoke(ctx)
        target = await self._resolve_user(ctx, user) or ctx.author
        random.seed(int(target.id))
        length = random.randint(1, 12)
        random.seed()
        await ctx.send(f"🍆 {target.display_name}'s penis is {length} inches long.\n`8{'=' * length}D`")

    @commands.command(name="ego")
    async def ego(self, ctx, *, user: str = None):
        await self._delete_invoke(ctx)
        target = await self._resolve_user(ctx, user) or ctx.author
        random.seed(int(target.id))
        percent = random.randint(0, 100)
        random.seed()
        bar = "█" * (percent // 10) + "░" * (10 - percent // 10)
        await ctx.send(f"👑 {target.display_name}'s ego is {percent}% massive.\n`[{bar}] {percent}%`")

    @commands.command(name="iqtest")
    async def iqtest(self, ctx, *, user: str = None):
        await self._delete_invoke(ctx)
        target = await self._resolve_user(ctx, user) or ctx.author
        random.seed(int(target.id))
        iq = random.randint(50, 200)
        random.seed()
        await ctx.send(f"🧠 {target.display_name}'s IQ is {iq}.")

    # ------------------------------------------------------------------ #
    # 7. hack
    # ------------------------------------------------------------------ #
    @commands.command(name="hack")
    async def hack(self, ctx, *, user: str = None):
        await self._delete_invoke(ctx)
        target = await self._resolve_user(ctx, user) or ctx.author
        msg = await ctx.send(f"```Initializing hack on {target.display_name}...```")

        ip = self._random_ip()
        password = random.choice(
            ["password123", "hunter2", "ilovecats", "admin",
             target.display_name.lower() + "123", "letmein", "123456", "qwerty"]
        )
        frames = [
            ("```[▘] Connecting to Discord API...```", 0.8),
            ("```[▝] Bypassing firewall...```", 1.0),
            ("```[▗] Accessing user data...```", 0.7),
            (f"```[▖] IP Address: {ip}```", 1.2),
            (f"```[▘] Email: {target.display_name.lower()}@gmail.com```", 0.8),
            (f"```[▝] Password: {password}```", 0.8),
            ("```[▗] Downloading browser history... 45%```", 1.0),
            ("```[▖] Downloading browser history... 78%```", 0.5),
            ("```[▘] Downloading browser history... 100%```", 0.5),
            ("```[▝] Accessing webcam...```", 1.5),
            ("```[▗] \U0001F4F8 Webcam snapshot saved```", 0.8),
            ("```[▖] Selling data to advertisers...```", 1.0),
            (f"```[✓] Hack complete. {target.display_name} has been hacked. \U0001F480\n\nJust kidding lol. This is fake.```", 0.0),
        ]
        for content, delay in frames:
            await asyncio.sleep(delay)
            await msg.edit(content=content)

    # ------------------------------------------------------------------ #
    # 8-14. simple random senders
    # ------------------------------------------------------------------ #
    @commands.command(name="insult")
    async def insult(self, ctx, *, _: str = None):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.INSULTS))

    @commands.command(name="dadjoke")
    async def dadjoke(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.DAD_JOKES))

    @commands.command(name="yomomma")
    async def yomomma(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.YO_MOMMA_JOKES))

    @commands.command(name="wouldyourather")
    async def wouldyourather(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.WOULD_YOU_RATHER))

    @commands.command(name="topic")
    async def topic(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.TOPICS))

    @commands.command(name="slot")
    async def slot(self, ctx):
        await self._delete_invoke(ctx)
        symbols = ["🍒", "🍋", "🍊", "🍇", "💎", "🔔", "7️⃣"]
        s1, s2, s3 = random.choice(symbols), random.choice(symbols), random.choice(symbols)
        result = f"🎰 | {s1} {s2} {s3} |"
        if s1 == s2 == s3:
            result += "\n🎉 **JACKPOT!**"
        elif s1 == s2 or s2 == s3 or s1 == s3:
            result += "\n✨ **Nice!**"
        else:
            result += "\n💨 **Try again!**"
        await ctx.send(result)

    @commands.command(name="advice")
    async def advice(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.ADVICE))

    # ------------------------------------------------------------------ #
    # 15-30. animal facts
    # ------------------------------------------------------------------ #
    @commands.command(name="catfact")
    async def catfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐱 {random.choice(self.CAT_FACTS)}")

    @commands.command(name="dogfact")
    async def dogfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐶 {random.choice(self.DOG_FACTS)}")

    @commands.command(name="pandafact")
    async def pandafact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐼 {random.choice(self.PANDA_FACTS)}")

    @commands.command(name="foxfact")
    async def foxfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🦊 {random.choice(self.FOX_FACTS)}")

    @commands.command(name="koalafact")
    async def koalafact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐨 {random.choice(self.KOALA_FACTS)}")

    @commands.command(name="birdfact")
    async def birdfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐦 {random.choice(self.BIRD_FACTS)}")

    @commands.command(name="redpandafact")
    async def redpandafact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"❤️ {random.choice(self.REDPANDA_FACTS)}")

    @commands.command(name="whalefact")
    async def whalefact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐳 {random.choice(self.WHALE_FACTS)}")

    @commands.command(name="kangaroofact")
    async def kangaroofact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🦘 {random.choice(self.KANGAROO_FACTS)}")

    @commands.command(name="bunnyfact")
    async def bunnyfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐰 {random.choice(self.BUNNY_FACTS)}")

    @commands.command(name="lionfact")
    async def lionfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🦁 {random.choice(self.LION_FACTS)}")

    @commands.command(name="frogfact")
    async def frogfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐸 {random.choice(self.FROG_FACTS)}")

    @commands.command(name="duckfact")
    async def duckfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🦆 {random.choice(self.DUCK_FACTS)}")

    @commands.command(name="penguinfact")
    async def penguinfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐧 {random.choice(self.PENGUIN_FACTS)}")

    @commands.command(name="dolphinfact")
    async def dolphinfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐬 {random.choice(self.DOLPHIN_FACTS)}")

    @commands.command(name="bearfact")
    async def bearfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🐻 {random.choice(self.BEAR_FACTS)}")

    @commands.command(name="axolotlfact")
    async def axolotlfact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🦎 {random.choice(self.AXOLOTL_FACTS)}")

    @commands.command(name="capybarafact")
    async def capybarafact(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f"🫎 {random.choice(self.CAPYBARA_FACTS)}")

    # ------------------------------------------------------------------ #
    # 31. trivia
    # ------------------------------------------------------------------ #
    @commands.command(name="trivia")
    async def trivia(self, ctx):
        await self._delete_invoke(ctx)
        question, answer = random.choice(self.TRIVIA)
        msg = await ctx.send(f"❓ **Question:** {question}")
        await asyncio.sleep(15)
        await msg.edit(content=f"❓ **Question:** {question}\n✅ **Answer:** {answer}")

    # ------------------------------------------------------------------ #
    # 32. dice
    # ------------------------------------------------------------------ #
    @commands.command(name="dice")
    async def dice(self, ctx, arg: str = None):
        await self._delete_invoke(ctx)
        count = 1
        sides = 6
        if arg:
            m = re.fullmatch(r"(\d+)d(\d+)", arg.strip())
            if m:
                count = min(int(m.group(1)), 100)
                sides = min(int(m.group(2)), 1000)
            elif arg.strip().isdigit():
                sides = min(int(arg.strip()), 1000)
            else:
                await ctx.send("Invalid dice format. Use `XdY` (e.g. `2d20`) or a number of sides.")
                return

        rolls = [random.randint(1, sides) for _ in range(count)]
        total = sum(rolls)
        if count == 1:
            await ctx.send(f"🎲 You rolled: **{rolls[0]}**")
        else:
            await ctx.send(f"🎲 Rolls: {rolls}\n**Total:** {total}")

    # ------------------------------------------------------------------ #
    # 33. randomemoji
    # ------------------------------------------------------------------ #
    @commands.command(name="randomemoji")
    async def randomemoji(self, ctx):
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.")
            return
        custom = list(ctx.guild.emojis)
        pool = custom + [discord.PartialEmoji(name=e, animated=False) for e in self.DEFAULT_EMOJIS]
        if not pool:
            await ctx.send("This server has no custom emojis.")
            return
        chosen = random.choice(pool)
        await ctx.send(str(chosen))

    # ------------------------------------------------------------------ #
    # 34. randomchannel
    # ------------------------------------------------------------------ #
    @commands.command(name="randomchannel")
    async def randomchannel(self, ctx):
        await self._delete_invoke(ctx)
        if ctx.guild is None:
            await ctx.send("This command can only be used in a server.")
            return
        channel = random.choice(ctx.guild.channels)
        await ctx.send(f"🎯 Random channel: {channel.mention}")

    # ------------------------------------------------------------------ #
    # 35. choose
    # ------------------------------------------------------------------ #
    @commands.command(name="choose")
    async def choose(self, ctx, *, options: str):
        await self._delete_invoke(ctx)
        if "," in options:
            opts = [o.strip() for o in options.split(",") if o.strip()]
        else:
            opts = options.split()
        if len(opts) < 2:
            await ctx.send("Give me at least 2 options to choose from.")
            return
        await ctx.send(f"🤔 I choose: **{random.choice(opts)}**")

    # ------------------------------------------------------------------ #
    # 36. poll
    # ------------------------------------------------------------------ #
    @commands.command(name="poll")
    async def poll(self, ctx, *, question: str):
        await self._delete_invoke(ctx)
        msg = await ctx.send(f"📊 **Poll:** {question}\n\nReact with 👍 or 👎")
        await msg.add_reaction("👍")
        await msg.add_reaction("👎")

    # ------------------------------------------------------------------ #
    # 37. numberfact
    # ------------------------------------------------------------------ #
    @commands.command(name="numberfact")
    async def numberfact(self, ctx, number: int):
        await self._delete_invoke(ctx)
        text = await self._api_get_text(f"http://numbersapi.com/{number}")
        if text:
            await ctx.send(text)
        else:
            await ctx.send("Could not fetch number fact.")

    # ------------------------------------------------------------------ #
    # 38. joke
    # ------------------------------------------------------------------ #
    @commands.command(name="joke")
    async def joke(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.JOKES))

    # ------------------------------------------------------------------ #
    # 39. fml
    # ------------------------------------------------------------------ #
    @commands.command(name="fml")
    async def fml(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.FML_QUOTES))

    # ------------------------------------------------------------------ #
    # 40. tronald
    # ------------------------------------------------------------------ #
    @commands.command(name="tronald")
    async def tronald(self, ctx):
        await self._delete_invoke(ctx)
        data = await self._api_get("https://api.tronalddump.io/random/quote")
        if data and data.get("value"):
            await ctx.send(f'"{data["value"]}" — Donald Trump')
        else:
            await ctx.send('"I have a great relationship with the Blacks." — Donald Trump')

    # ------------------------------------------------------------------ #
    # 41. kanyewest
    # ------------------------------------------------------------------ #
    @commands.command(name="kanyewest")
    async def kanyewest(self, ctx):
        await self._delete_invoke(ctx)
        data = await self._api_get("https://api.kanye.rest/")
        if data and data.get("quote"):
            await ctx.send(f'"{data["quote"]}" — Kanye West')
        else:
            await ctx.send('"I\'m a creative genius." — Kanye West')

    # ------------------------------------------------------------------ #
    # 42. rps
    # ------------------------------------------------------------------ #
    @commands.command(name="rps")
    async def rps(self, ctx, choice: str):
        await self._delete_invoke(ctx)
        mapping = {"rock": "r", "paper": "p", "scissors": "s", "r": "r", "p": "p", "s": "s"}
        uc = mapping.get(choice.strip().lower())
        if not uc:
            await ctx.send("Choose `rock`, `paper`, or `scissors` (or r/p/s).")
            return
        bot_choice = random.choice(["r", "p", "s"])
        names = {"r": "Rock", "p": "Paper", "s": "Scissors"}
        if uc == bot_choice:
            result = "It's a tie"
        elif (uc == "r" and bot_choice == "s") or (uc == "s" and bot_choice == "p") or (uc == "p" and bot_choice == "r"):
            result = "You win"
        else:
            result = "I win"
        await ctx.send(
            f"You chose **{names[uc]}**. I chose **{names[bot_choice]}**. {result}!"
        )

    # ------------------------------------------------------------------ #
    # 43. covidtest
    # ------------------------------------------------------------------ #
    @commands.command(name="covidtest")
    async def covidtest(self, ctx, *, user: str = None):
        await self._delete_invoke(ctx)
        target = await self._resolve_user(ctx, user) or ctx.author
        roll = random.random()
        if roll < 0.70:
            result = "Negative"
            flavor = "You're in the clear (probably)."
        elif roll < 0.95:
            result = "Positive"
            flavor = "Isolate yourself and drink some water."
        else:
            result = "Inconclusive"
            flavor = "Please test again tomorrow."
        await ctx.send(f"🦠 COVID Test for {target.display_name}: **{result}**\n{flavor}")

    # ------------------------------------------------------------------ #
    # 44-50. social commands
    # ------------------------------------------------------------------ #
    async def _social(self, ctx, user: str, action: str):
        await self._delete_invoke(ctx)
        target = await self._resolve_user(ctx, user)
        if not target:
            await ctx.send("Could not find that user.")
            return
        url = None
        data = await self._api_get(f"https://api.nekos.dev/api/v3/images/sfw/img/{action}/")
        if data:
            try:
                url = data["data"]["response"]["image_url"]
            except (KeyError, TypeError):
                url = None
        if not url:
            url = random.choice(self.SOCIAL_FALLBACK.get(action, [self.SOCIAL_FALLBACK["hug"][0]]))
        embed = discord.Embed(
            description=f"{ctx.author.display_name} {action}s {target.display_name}!",
            color=discord.Color.random(),
        )
        embed.set_image(url=url)
        await ctx.send(embed=embed)

    @commands.command(name="hug")
    async def hug(self, ctx, *, user: str):
        await self._social(ctx, user, "hug")

    @commands.command(name="kiss")
    async def kiss(self, ctx, *, user: str):
        await self._social(ctx, user, "kiss")

    @commands.command(name="slap")
    async def slap(self, ctx, *, user: str):
        await self._social(ctx, user, "slap")

    @commands.command(name="cuddle")
    async def cuddle(self, ctx, *, user: str):
        await self._social(ctx, user, "cuddle")

    @commands.command(name="pat")
    async def pat(self, ctx, *, user: str):
        await self._social(ctx, user, "pat")

    @commands.command(name="feed")
    async def feed(self, ctx, *, user: str):
        await self._social(ctx, user, "feed")

    @commands.command(name="wink")
    async def wink(self, ctx, *, user: str):
        await self._social(ctx, user, "wink")

    # ------------------------------------------------------------------ #
    # 51. chucknorris
    # ------------------------------------------------------------------ #
    @commands.command(name="chucknorris")
    async def chucknorris(self, ctx):
        await self._delete_invoke(ctx)
        data = await self._api_get("https://api.chucknorris.io/jokes/random")
        joke = data.get("value") if data else None
        if not joke:
            joke = random.choice(self.CHUCK_NORRIS)
        await ctx.send(joke)

    # ------------------------------------------------------------------ #
    # 52. iss
    # ------------------------------------------------------------------ #
    @commands.command(name="iss")
    async def iss(self, ctx):
        await self._delete_invoke(ctx)
        data = await self._api_get("http://api.open-notify.org/iss-now.json")
        if not data:
            await ctx.send("Could not fetch ISS position.")
            return
        try:
            pos = data["iss_position"]
            lat = pos["latitude"]
            lon = pos["longitude"]
        except (KeyError, TypeError):
            await ctx.send("Could not fetch ISS position.")
            return
        await ctx.send(
            f"🛰️ **ISS Current Position**\nLatitude: {lat}\nLongitude: {lon}\n"
            f"📍 Maps: https://maps.google.com/?q={lat},{lon}"
        )

    # ------------------------------------------------------------------ #
    # 53. apod
    # ------------------------------------------------------------------ #
    @commands.command(name="apod")
    async def apod(self, ctx):
        await self._delete_invoke(ctx)
        data = await self._api_get("https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY")
        if not data:
            await ctx.send("Could not fetch APOD.")
            return
        title = data.get("title", "Astronomy Picture of the Day")
        url = data.get("url", "")
        explanation = data.get("explanation", "")
        date = data.get("date", "")
        if len(explanation) > 500:
            explanation = explanation[:497] + "..."
        embed = discord.Embed(title=title, description=explanation, color=discord.Color.blue())
        embed.set_image(url=url)
        embed.set_footer(text=f"NASA APOD • {date}")
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------ #
    # 54. httpcat
    # ------------------------------------------------------------------ #
    @commands.command(name="httpcat")
    async def httpcat(self, ctx, status: int):
        await self._delete_invoke(ctx)
        if not (100 <= status <= 599):
            await ctx.send("Please provide a valid HTTP status code (100-599).")
            return
        img_url = f"https://http.cat/{status}.jpg"
        embed = discord.Embed(title=f"HTTP {status}", color=discord.Color.orange())
        embed.set_image(url=img_url)
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------ #
    # 55. riddle
    # ------------------------------------------------------------------ #
    @commands.command(name="riddle")
    async def riddle(self, ctx):
        await self._delete_invoke(ctx)
        question, answer = random.choice(self.RIDDLES)
        msg = await ctx.send(f"❓ **Riddle:** {question}")
        await asyncio.sleep(20)
        await msg.edit(content=f"❓ **Riddle:** {question}\n💡 **Answer:** {answer}")

    # ------------------------------------------------------------------ #
    # 56. quote
    # ------------------------------------------------------------------ #
    @commands.command(name="quote")
    async def quote(self, ctx):
        await self._delete_invoke(ctx)
        text, author = random.choice(self.QUOTES)
        await ctx.send(f'"{text}" — **{author}**')

    # ------------------------------------------------------------------ #
    # 57. evilinsult
    # ------------------------------------------------------------------ #
    @commands.command(name="evilinsult")
    async def evilinsult(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.EVIL_INSULTS))

    # ------------------------------------------------------------------ #
    # 58. owoify
    # ------------------------------------------------------------------ #
    @commands.command(name="owoify")
    async def owoify(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        out = text
        out = re.sub(r"[rl]", "w", out)
        out = re.sub(r"[RL]", "W", out)
        out = re.sub(r"n([aeiouAEIOU])", r"ny\1", out)
        out = re.sub(r"ove", "uv", out)
        out = out.replace("!", " (｡◕‿◕｡)")
        out = out.replace("?", " owo?")
        if random.random() < 0.5:
            out += " ~"
        else:
            out += " uwu"
        await ctx.send(out)

    # ------------------------------------------------------------------ #
    # 59. uwuify
    # ------------------------------------------------------------------ #
    @commands.command(name="uwuify")
    async def uwuify(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        out = "uwu " + text
        out = re.sub(r"[rl]", "w", out)
        out = re.sub(r"[RL]", "W", out)
        out = re.sub(r"a", "aa", out) if random.random() < 0.5 else out
        out = re.sub(r"e", "ee", out) if random.random() < 0.5 else out
        out += "~"
        await ctx.send(out)

    # ------------------------------------------------------------------ #
    # 60. uvuify
    # ------------------------------------------------------------------ #
    @commands.command(name="uvuify")
    async def uvuify(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        out = "uvu " + text
        out = re.sub(r"[rl]", "v", out)
        out = re.sub(r"[RL]", "V", out)
        out = out.replace(" ", " ✨ ")
        await ctx.send(out)

    # ------------------------------------------------------------------ #
    # 61. rickrollurl
    # ------------------------------------------------------------------ #
    @commands.command(name="rickrollurl")
    async def rickrollurl(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    # ------------------------------------------------------------------ #
    # 62. rickroll
    # ------------------------------------------------------------------ #
    @commands.command(name="rickroll")
    async def rickroll(self, ctx):
        await self._delete_invoke(ctx)
        msg = await ctx.send(self.RICK_ROLL_LYRICS[0])
        for line in self.RICK_ROLL_LYRICS[1:]:
            await asyncio.sleep(1.5)
            await msg.edit(content=line)

    # ------------------------------------------------------------------ #
    # 63. coinflip
    # ------------------------------------------------------------------ #
    @commands.command(name="coinflip")
    async def coinflip(self, ctx):
        await self._delete_invoke(ctx)
        msg = await ctx.send("🪙 Flipping...")
        await asyncio.sleep(1)
        result = random.choice(["Heads", "Tails"])
        await msg.edit(content=f"🪙 **{result}!**")

    # ------------------------------------------------------------------ #
    # 64. notfunny
    # ------------------------------------------------------------------ #
    @commands.command(name="notfunny")
    async def notfunny(self, ctx):
        await self._delete_invoke(ctx)
        text = self.NOT_FUNNY_COPYPASTA
        if len(text) <= 2000:
            await ctx.send(text)
        else:
            for i in range(0, len(text), 2000):
                await ctx.send(text[i:i + 2000])

    # ------------------------------------------------------------------ #
    # 65. randomquestion
    # ------------------------------------------------------------------ #
    @commands.command(name="randomquestion")
    async def randomquestion(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.RANDOM_QUESTIONS))

    # ------------------------------------------------------------------ #
    # 66. lyrics
    # ------------------------------------------------------------------ #
    @commands.command(name="lyrics")
    async def lyrics(self, ctx, *, query: str):
        await self._delete_invoke(ctx)
        if " - " in query:
            artist, title = query.split(" - ", 1)
        else:
            parts = query.split(None, 1)
            if len(parts) < 2:
                await ctx.send("Usage: `.lyrics <artist> - <title>` or `.lyrics <artist> <title>`")
                return
            artist, title = parts[0], parts[1]
        data = await self._api_get(f"https://api.lyrics.ovh/v1/{artist}/{title}")
        if not data or not data.get("lyrics"):
            await ctx.send("Lyrics not found.")
            return
        text = data["lyrics"]
        if len(text) <= 2000:
            await ctx.send(f"**{title}** by **{artist}**\n\n{text}")
        else:
            await ctx.send(f"**{title}** by **{artist}**")
            for i in range(0, len(text), 2000):
                await ctx.send(text[i:i + 2000])

    # ------------------------------------------------------------------ #
    # 67-70. TV show quotes
    # ------------------------------------------------------------------ #
    @commands.command(name="breakingbadquote")
    async def breakingbadquote(self, ctx):
        await self._delete_invoke(ctx)
        data = await self._api_get("https://api.breakingbadquotes.xyz/v1/quotes")
        if isinstance(data, list) and data and data[0].get("quote"):
            q = data[0]
            await ctx.send(f'"{q["quote"]}" — **{q.get("author", "Walter White")}**')
        else:
            await ctx.send('"I am the one who knocks." — **Walter White**')

    @commands.command(name="gameofthronesquote")
    async def gameofthronesquote(self, ctx):
        await self._delete_invoke(ctx)
        data = await self._api_get("https://api.gameofthronesquotes.xyz/v1/random")
        if data and data.get("sentence"):
            char = data.get("character", {}).get("name", "Unknown")
            await ctx.send(f'"{data["sentence"]}" — **{char}**')
        else:
            await ctx.send('"Winter is coming." — **Ned Stark**')

    @commands.command(name="luciferquote")
    async def luciferquote(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.LUCIFER_QUOTES))

    @commands.command(name="strangerthingsquote")
    async def strangerthingsquote(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.STRANGER_THINGS_QUOTES))

    # ------------------------------------------------------------------ #
    # 71. xkcd
    # ------------------------------------------------------------------ #
    @commands.command(name="xkcd")
    async def xkcd(self, ctx, number: int = None):
        await self._delete_invoke(ctx)
        url = f"https://xkcd.com/{number}/info.0.json" if number else "https://xkcd.com/info.0.json"
        data = await self._api_get(url)
        if not data:
            await ctx.send("Could not fetch XKCD comic.")
            return
        embed = discord.Embed(title=f"{data.get('num')}: {data.get('title')}", color=discord.Color.blurple())
        embed.set_image(url=data.get("img", ""))
        embed.set_footer(text=data.get("alt", ""))
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------ #
    # 72. boredactivity
    # ------------------------------------------------------------------ #
    @commands.command(name="boredactivity")
    async def boredactivity(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.BORED_ACTIVITIES))

    # ------------------------------------------------------------------ #
    # 73. ermahgerd
    # ------------------------------------------------------------------ #
    @commands.command(name="ermahgerd")
    async def ermahgerd(self, ctx, *, text: str):
        await self._delete_invoke(ctx)
        out = text.lower()
        out = out.replace("er", "er").replace("ar", "er").replace("or", "er")
        out = re.sub(r"\b([aeo])(?=\w)", "er", out)
        out = out.replace("my", "mah").replace("you", "yu").replace("the", "ther")
        out = "ERMAHGERD! " + out
        await ctx.send(out)

    # ------------------------------------------------------------------ #
    # 74. iseven
    # ------------------------------------------------------------------ #
    @commands.command(name="iseven")
    async def iseven(self, ctx, number: int):
        await self._delete_invoke(ctx)
        if number % 2 == 0:
            await ctx.send(f"✅ {number} is even.")
        else:
            await ctx.send(f"❌ {number} is odd.")

    # ------------------------------------------------------------------ #
    # 75. agify
    # ------------------------------------------------------------------ #
    @commands.command(name="agify")
    async def agify(self, ctx, *, name: str):
        await self._delete_invoke(ctx)
        data = await self._api_get(f"https://api.agify.io/?name={name}")
        if data and data.get("age") is not None:
            age = data["age"]
            count = data.get("count", 0)
            await ctx.send(
                f"👤 The estimated age for the name **{name}** is **{age}** years old. (based on {count} data points)"
            )
        else:
            await ctx.send("Could not estimate age.")

    # ------------------------------------------------------------------ #
    # 76. randomword
    # ------------------------------------------------------------------ #
    @commands.command(name="randomword")
    async def randomword(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.RANDOM_WORDS))

    # ------------------------------------------------------------------ #
    # 77. randomweirdword
    # ------------------------------------------------------------------ #
    @commands.command(name="randomweirdword")
    async def randomweirdword(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.WEIRD_WORDS))

    # ------------------------------------------------------------------ #
    # 78. startupidea
    # ------------------------------------------------------------------ #
    @commands.command(name="startupidea")
    async def startupidea(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.STARTUP_IDEAS))

    # ------------------------------------------------------------------ #
    # 79. fakeperson
    # ------------------------------------------------------------------ #
    @commands.command(name="fakeperson")
    async def fakeperson(self, ctx):
        await self._delete_invoke(ctx)
        try:
            async with self.session.get(
                "https://thispersondoesnotexist.com/image",
                timeout=aiohttp.ClientTimeout(total=15),
                headers={"User-Agent": "Mozilla/5.0"},
            ) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    await ctx.send(
                        "Here's a face that doesn't exist:",
                        file=discord.File(io.BytesIO(data), filename="fakeperson.jpg"),
                    )
                    return
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        await ctx.send("https://thispersondoesnotexist.com/")

    # ------------------------------------------------------------------ #
    # 80. commitmessage
    # ------------------------------------------------------------------ #
    @commands.command(name="commitmessage")
    async def commitmessage(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(f'git commit -m "{random.choice(self.COMMIT_MESSAGES)}"')

    # ------------------------------------------------------------------ #
    # 81. showerthought
    # ------------------------------------------------------------------ #
    @commands.command(name="showerthought")
    async def showerthought(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.SHOWER_THOUGHTS))

    # ------------------------------------------------------------------ #
    # 82-85. party game commands
    # ------------------------------------------------------------------ #
    @commands.command(name="truth")
    async def truth(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.TRUTH_QUESTIONS))

    @commands.command(name="dare")
    async def dare(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.DARE_CHALLENGES))

    @commands.command(name="neverhaveiever")
    async def neverhaveiever(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.NEVER_HAVE_I_EVER))

    @commands.command(name="paranoia")
    async def paranoia(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.PARANOIA_QUESTIONS))

    # ------------------------------------------------------------------ #
    # 86. randomcolor
    # ------------------------------------------------------------------ #
    @commands.command(name="randomcolor")
    async def randomcolor(self, ctx):
        await self._delete_invoke(ctx)
        r, g, b = random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
        hex_code = f"#{r:02X}{g:02X}{b:02X}"
        embed = discord.Embed(
            title=f"Random Color: {hex_code}",
            description=f"RGB: `{r}, {g}, {b}`",
            color=discord.Color.from_rgb(r, g, b),
        )
        embed.add_field(name="Hex", value=hex_code, inline=True)
        embed.add_field(name="RGB", value=f"{r}, {g}, {b}", inline=True)
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------ #
    # 87. pickupline
    # ------------------------------------------------------------------ #
    @commands.command(name="pickupline")
    async def pickupline(self, ctx):
        await self._delete_invoke(ctx)
        await ctx.send(random.choice(self.PICKUP_LINES))

    # ------------------------------------------------------------------ #
    # 88. elementinfo
    # ------------------------------------------------------------------ #
    @commands.command(name="elementinfo")
    async def elementinfo(self, ctx, *, element: str):
        await self._delete_invoke(ctx)
        info = self._element_lookup(element)
        if not info:
            await ctx.send(f"Could not find an element matching `{element}`.")
            return
        embed = discord.Embed(
            title=f"{info['name']} ({info['symbol']})",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Atomic Number", value=info["number"], inline=True)
        embed.add_field(name="Symbol", value=info["symbol"], inline=True)
        embed.add_field(name="Atomic Mass", value=f"{info['mass']} u", inline=True)
        embed.add_field(name="Category", value=info["category"], inline=True)
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------ #
    # 89. randomelement
    # ------------------------------------------------------------------ #
    @commands.command(name="randomelement")
    async def randomelement(self, ctx):
        await self._delete_invoke(ctx)
        info = random.choice(self.ELEMENT_DATA)
        embed = discord.Embed(
            title=f"{info[1]} ({info[2]})",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Atomic Number", value=info[0], inline=True)
        embed.add_field(name="Symbol", value=info[2], inline=True)
        embed.add_field(name="Atomic Mass", value=f"{info[3]} u", inline=True)
        embed.add_field(name="Category", value=info[4], inline=True)
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(FunCommands(bot))
