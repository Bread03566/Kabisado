import React, { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';

/*
 * The study-buddy animals. One chosen animal is the app's mascot everywhere: the navbar
 * logo, the hero banners, empty states, and the corner pet (Companion.jsx).
 *
 * Each animal is SVG art in a 120x120 box plus a list of eyes. Eyes are drawn by shared
 * code so cursor tracking, blinking, moods, and glasses work the same for every animal.
 */

const DARK = '#2B1D14';

export const ANIMALS = {
  cat: {
    name: 'Orange cat',
    emoji: '🐱',
    sounds: ['Prrr... you got this!', 'Mrow! One more section?', '*slow blink* proud of you', 'Purr. Stay hydrated!'],
    eyes: [{ cx: 47, cy: 50, r: 7.5 }, { cx: 73, cy: 50, r: 7.5 }],
    eyeWhite: '#A4CF5E',
    pupil: 'slit',
    tail: (
      <g className="pet-tail" style={{ transformOrigin: '86px 100px' }}>
        <path d="M86 100 C 108 98, 112 72, 99 62" stroke="#E8A35A" strokeWidth="9" fill="none" strokeLinecap="round" />
        <path d="M86 100 C 108 98, 112 72, 99 62" stroke="#B8692E" strokeWidth="9" fill="none" strokeLinecap="round" strokeDasharray="3 7" />
      </g>
    ),
    body: (
      <>
        <ellipse cx="60" cy="98" rx="30" ry="20" fill="#E8A35A" />
        <path d="M40 92 q4 6 0 12 M80 92 q-4 6 0 12" stroke="#B8692E" strokeWidth="3" fill="none" strokeLinecap="round" />
        <ellipse cx="60" cy="103" rx="15" ry="12" fill="#FBE9D7" />
        <ellipse cx="48" cy="114" rx="8" ry="5" fill="#FBE9D7" />
        <ellipse cx="72" cy="114" rx="8" ry="5" fill="#FBE9D7" />
      </>
    ),
    head: (
      <>
        <polygon points="29,40 33,9 55,28" fill="#E8A35A" />
        <polygon points="35,33 37,17 48,28" fill="#F4B6B6" />
        <polygon points="91,40 87,9 65,28" fill="#E8A35A" />
        <polygon points="85,33 83,17 72,28" fill="#F4B6B6" />
        <ellipse cx="60" cy="54" rx="34" ry="30" fill="#E8A35A" />
        <path d="M48 29 l4 10 M60 26 v12 M72 29 l-4 10" stroke="#B8692E" strokeWidth="3.5" strokeLinecap="round" />
        <path d="M27 54 h9 M28 61 h8 M93 54 h-9 M92 61 h-8" stroke="#B8692E" strokeWidth="3" strokeLinecap="round" />
        <ellipse cx="60" cy="67" rx="14" ry="10" fill="#FBE9D7" />
        <circle cx="38" cy="63" r="4" fill="#F4A6A6" opacity="0.55" />
        <circle cx="82" cy="63" r="4" fill="#F4A6A6" opacity="0.55" />
        <path d="M56 61 h8 l-4 4 z" fill="#E57B8A" />
        <path d="M60 65 v3 M60 68 q-4 4 -7 1 M60 68 q4 4 7 1" stroke="#6B3E1F" strokeWidth="1.6" fill="none" strokeLinecap="round" />
        <path d="M44 66 l-16 -3 M44 69 l-16 2 M76 66 l16 -3 M76 69 l16 2" stroke="#6B3E1F" strokeWidth="1" opacity="0.6" strokeLinecap="round" />
      </>
    ),
  },
  dog: {
    name: 'Shiba dog',
    emoji: '🐶',
    sounds: ['Woof! You are doing great!', '*tail wag intensifies*', 'Arf! Treat after this quiz?', 'Bork! Keep going!'],
    eyes: [{ cx: 47, cy: 51, r: 6.5 }, { cx: 73, cy: 51, r: 6.5 }],
    eyeWhite: '#FFFFFF',
    iris: '#5A3A22',
    pupil: 'round',
    tail: (
      <g className="pet-tail" style={{ transformOrigin: '86px 98px' }}>
        <path d="M86 98 C 106 94, 110 74, 96 71 C 87 70, 88 82, 97 80" stroke="#D9894A" strokeWidth="8" fill="none" strokeLinecap="round" />
      </g>
    ),
    body: (
      <>
        <ellipse cx="60" cy="98" rx="30" ry="20" fill="#D9894A" />
        <ellipse cx="60" cy="103" rx="16" ry="13" fill="#FFF3E6" />
        <ellipse cx="48" cy="114" rx="8" ry="5" fill="#FFF3E6" />
        <ellipse cx="72" cy="114" rx="8" ry="5" fill="#FFF3E6" />
      </>
    ),
    head: (
      <>
        <polygon points="29,42 35,11 55,30" fill="#D9894A" />
        <polygon points="36,35 38,21 48,30" fill="#FFF3E6" />
        <polygon points="91,42 85,11 65,30" fill="#D9894A" />
        <polygon points="84,35 82,21 72,30" fill="#FFF3E6" />
        <ellipse cx="60" cy="54" rx="34" ry="30" fill="#D9894A" />
        <ellipse cx="60" cy="66" rx="23" ry="17" fill="#FFF3E6" />
        <circle cx="46" cy="40" r="2.6" fill="#FFF3E6" />
        <circle cx="74" cy="40" r="2.6" fill="#FFF3E6" />
        <ellipse cx="60" cy="61" rx="5.5" ry="3.8" fill={DARK} />
        <path d="M60 64 v3 M60 67 q-5 5 -9 1 M60 67 q5 5 9 1" stroke={DARK} strokeWidth="1.6" fill="none" strokeLinecap="round" />
        <circle cx="37" cy="64" r="4" fill="#F4A6A6" opacity="0.5" />
        <circle cx="83" cy="64" r="4" fill="#F4A6A6" opacity="0.5" />
      </>
    ),
  },
  bunny: {
    name: 'Bunny',
    emoji: '🐰',
    sounds: ['*happy hop*', 'Nom... carrot break later?', '*twitches nose encouragingly*', 'Hop to the next topic!'],
    eyes: [{ cx: 48, cy: 55, r: 6.5 }, { cx: 72, cy: 55, r: 6.5 }],
    eyeWhite: '#FFFFFF',
    iris: '#3B2F2F',
    pupil: 'round',
    tail: <circle cx="89" cy="105" r="7" fill="#FFFFFF" stroke="#CFC4BE" strokeWidth="1.5" />,
    body: (
      <>
        <ellipse cx="60" cy="99" rx="28" ry="19" fill="#EDE7E3" stroke="#CFC4BE" strokeWidth="1.5" />
        <ellipse cx="60" cy="103" rx="14" ry="11" fill="#FFFFFF" />
        <ellipse cx="47" cy="114" rx="9" ry="5" fill="#FFFFFF" stroke="#CFC4BE" strokeWidth="1.2" />
        <ellipse cx="73" cy="114" rx="9" ry="5" fill="#FFFFFF" stroke="#CFC4BE" strokeWidth="1.2" />
      </>
    ),
    head: (
      <>
        <g className="pet-ear-left" style={{ transformOrigin: '47px 36px' }}>
          <ellipse cx="45" cy="18" rx="8" ry="22" fill="#EDE7E3" stroke="#CFC4BE" strokeWidth="1.5" transform="rotate(-12 45 18)" />
          <ellipse cx="45" cy="20" rx="4" ry="15" fill="#F6BFC8" transform="rotate(-12 45 18)" />
        </g>
        <ellipse cx="75" cy="18" rx="8" ry="22" fill="#EDE7E3" stroke="#CFC4BE" strokeWidth="1.5" transform="rotate(12 75 18)" />
        <ellipse cx="75" cy="20" rx="4" ry="15" fill="#F6BFC8" transform="rotate(12 75 18)" />
        <ellipse cx="60" cy="58" rx="30" ry="27" fill="#EDE7E3" stroke="#CFC4BE" strokeWidth="1.5" />
        <ellipse cx="60" cy="69" rx="12" ry="8" fill="#FFFFFF" />
        <path d="M57 64 h6 l-3 3 z" fill="#E88A9B" />
        <path d="M60 67 v2 M60 69 q-3 3 -6 1 M60 69 q3 3 6 1" stroke="#7A6A64" strokeWidth="1.4" fill="none" strokeLinecap="round" />
        <path d="M47 68 l-13 -2 M47 71 l-13 2 M73 68 l13 -2 M73 71 l13 2" stroke="#7A6A64" strokeWidth="0.9" opacity="0.6" strokeLinecap="round" />
        <circle cx="40" cy="66" r="4" fill="#F4A6A6" opacity="0.55" />
        <circle cx="80" cy="66" r="4" fill="#F4A6A6" opacity="0.55" />
      </>
    ),
  },
  seal: {
    name: 'Seal',
    emoji: '🦭',
    sounds: ['Arf arf! *flipper clap*', '*happy seal noises*', 'Blub! Keep swimming through it!', 'You will seal the deal on this exam!'],
    eyes: [{ cx: 47, cy: 50, r: 7.5 }, { cx: 73, cy: 50, r: 7.5 }],
    eyeWhite: '#FFFFFF',
    iris: '#1E1E1E',
    pupil: 'round',
    tail: (
      <g className="pet-tail" style={{ transformOrigin: '76px 110px' }}>
        <path d="M76 110 q14 8 20 -1 q-8 -1 -12 -8 z" fill="#7E8A94" />
      </g>
    ),
    body: (
      <>
        <ellipse cx="60" cy="96" rx="28" ry="22" fill="#9AA5AE" />
        <ellipse cx="60" cy="101" rx="17" ry="15" fill="#C9D1D7" />
        <circle cx="45" cy="88" r="2.2" fill="#7E8A94" opacity="0.7" />
        <circle cx="74" cy="92" r="1.8" fill="#7E8A94" opacity="0.7" />
        <circle cx="68" cy="84" r="1.5" fill="#7E8A94" opacity="0.7" />
        <ellipse cx="37" cy="104" rx="5" ry="11" fill="#7E8A94" transform="rotate(28 37 104)" />
        <ellipse cx="83" cy="104" rx="5" ry="11" fill="#7E8A94" transform="rotate(-28 83 104)" />
      </>
    ),
    head: (
      <>
        <ellipse cx="60" cy="54" rx="32" ry="29" fill="#9AA5AE" />
        <circle cx="42" cy="37" r="2" fill="#7E8A94" />
        <circle cx="79" cy="39" r="1.6" fill="#7E8A94" />
        <circle cx="66" cy="31" r="1.4" fill="#7E8A94" />
        <circle cx="53" cy="66" r="8" fill="#C9D1D7" />
        <circle cx="67" cy="66" r="8" fill="#C9D1D7" />
        <ellipse cx="60" cy="61" rx="4.5" ry="3" fill={DARK} />
        <path d="M60 64 v3" stroke={DARK} strokeWidth="1.5" strokeLinecap="round" />
        <circle cx="50" cy="66" r="0.9" fill="#5B6670" />
        <circle cx="54" cy="69" r="0.9" fill="#5B6670" />
        <circle cx="70" cy="66" r="0.9" fill="#5B6670" />
        <circle cx="66" cy="69" r="0.9" fill="#5B6670" />
        <path d="M48 66 l-15 -3 M48 69 l-15 2 M72 66 l15 -3 M72 69 l15 2" stroke="#5B6670" strokeWidth="0.9" opacity="0.7" strokeLinecap="round" />
        <circle cx="38" cy="60" r="4" fill="#F4A6A6" opacity="0.45" />
        <circle cx="82" cy="60" r="4" fill="#F4A6A6" opacity="0.45" />
      </>
    ),
  },
  sealion: {
    name: 'Sea lion',
    emoji: '🦭',
    sounds: ['Ar-ar-ar! *barks proudly*', '*balances your notes on its nose*', 'Sea lion says: one more card!', 'Honk! You are doing great!'],
    eyes: [{ cx: 49, cy: 48, r: 6.5 }, { cx: 71, cy: 48, r: 6.5 }],
    eyeWhite: '#FFFFFF',
    iris: '#2A1A10',
    pupil: 'round',
    tail: <path d="M74 112 q16 6 21 -3 q-9 0 -13 -7 z" fill="#5E3D26" />,
    body: (
      <>
        <ellipse cx="60" cy="98" rx="26" ry="21" fill="#8B5E3C" />
        <ellipse cx="60" cy="100" rx="15" ry="16" fill="#A9764F" />
        <ellipse cx="35" cy="108" rx="6" ry="14" fill="#5E3D26" transform="rotate(42 35 108)" />
        <ellipse cx="85" cy="108" rx="6" ry="14" fill="#5E3D26" transform="rotate(-42 85 108)" />
      </>
    ),
    head: (
      <>
        <rect x="45" y="66" width="30" height="16" fill="#8B5E3C" />
        <ellipse cx="60" cy="50" rx="27" ry="26" fill="#8B5E3C" />
        <ellipse cx="34" cy="47" rx="2.6" ry="4.5" fill="#5E3D26" />
        <ellipse cx="86" cy="47" rx="2.6" ry="4.5" fill="#5E3D26" />
        <ellipse cx="60" cy="64" rx="13" ry="9" fill="#A9764F" />
        <ellipse cx="60" cy="59" rx="4" ry="2.6" fill={DARK} />
        <path d="M60 62 v2 M60 64 q-4 3 -7 0 M60 64 q4 3 7 0" stroke={DARK} strokeWidth="1.4" fill="none" strokeLinecap="round" />
        <path d="M49 63 l-17 -4 M49 66 l-17 1 M71 63 l17 -4 M71 66 l17 1" stroke="#EADBC8" strokeWidth="1" strokeLinecap="round" />
      </>
    ),
  },
  panda: {
    name: 'Panda',
    emoji: '🐼',
    sounds: ['*munches bamboo thoughtfully*', 'Panda power! Keep going!', '*rolls over* ...okay, back to studying', 'Bamboo break after this section?'],
    eyes: [{ cx: 47, cy: 52, r: 5 }, { cx: 73, cy: 52, r: 5 }],
    eyeWhite: '#FFFFFF',
    iris: '#2B2B2B',
    pupil: 'round',
    tail: null,
    body: (
      <>
        <ellipse cx="60" cy="98" rx="29" ry="20" fill="#FFFFFF" stroke="#D9D9D9" strokeWidth="1.5" />
        <ellipse cx="38" cy="97" rx="8" ry="13" fill="#2B2B2B" transform="rotate(22 38 97)" />
        <ellipse cx="82" cy="97" rx="8" ry="13" fill="#2B2B2B" transform="rotate(-22 82 97)" />
        <ellipse cx="47" cy="114" rx="9" ry="5" fill="#2B2B2B" />
        <ellipse cx="73" cy="114" rx="9" ry="5" fill="#2B2B2B" />
      </>
    ),
    head: (
      <>
        <circle cx="35" cy="30" r="9" fill="#2B2B2B" />
        <circle cx="85" cy="30" r="9" fill="#2B2B2B" />
        <ellipse cx="60" cy="55" rx="33" ry="29" fill="#FFFFFF" stroke="#D9D9D9" strokeWidth="1.5" />
        <ellipse cx="46" cy="53" rx="9" ry="11" fill="#2B2B2B" transform="rotate(-28 46 53)" />
        <ellipse cx="74" cy="53" rx="9" ry="11" fill="#2B2B2B" transform="rotate(28 74 53)" />
        <ellipse cx="60" cy="67" rx="11" ry="8" fill="#FFFFFF" />
        <ellipse cx="60" cy="63" rx="4.5" ry="3" fill="#2B2B2B" />
        <path d="M60 66 v2 M60 68 q-4 3 -7 0 M60 68 q4 3 7 0" stroke="#2B2B2B" strokeWidth="1.4" fill="none" strokeLinecap="round" />
        <circle cx="38" cy="66" r="4" fill="#F4A6A6" opacity="0.5" />
        <circle cx="82" cy="66" r="4" fill="#F4A6A6" opacity="0.5" />
      </>
    ),
  },
  penguin: {
    name: 'Penguin',
    emoji: '🐧',
    sounds: ['*waddles excitedly*', 'Noot noot! Keep studying!', 'Cool as ice. You got this.', 'Slide into that next quiz!'],
    eyes: [{ cx: 49, cy: 53, r: 5.5 }, { cx: 71, cy: 53, r: 5.5 }],
    eyeWhite: '#FFFFFF',
    iris: '#1E1E1E',
    pupil: 'round',
    tail: null,
    body: (
      <>
        <ellipse cx="34" cy="96" rx="5" ry="14" fill="#2F3A45" transform="rotate(22 34 96)" />
        <ellipse cx="86" cy="96" rx="5" ry="14" fill="#2F3A45" transform="rotate(-22 86 96)" />
        <ellipse cx="60" cy="96" rx="27" ry="22" fill="#2F3A45" />
        <ellipse cx="60" cy="100" rx="18" ry="17" fill="#FFFFFF" />
        <ellipse cx="50" cy="116" rx="7" ry="3.5" fill="#F2A33A" />
        <ellipse cx="70" cy="116" rx="7" ry="3.5" fill="#F2A33A" />
      </>
    ),
    head: (
      <>
        <ellipse cx="60" cy="54" rx="31" ry="28" fill="#2F3A45" />
        <circle cx="49" cy="57" r="13" fill="#FFFFFF" />
        <circle cx="71" cy="57" r="13" fill="#FFFFFF" />
        <ellipse cx="60" cy="65" rx="16" ry="12" fill="#FFFFFF" />
        <path d="M55 61 L65 61 L60 68 Z" fill="#F2A33A" />
        <circle cx="41" cy="65" r="3.5" fill="#F4A6A6" opacity="0.55" />
        <circle cx="79" cy="65" r="3.5" fill="#F4A6A6" opacity="0.55" />
      </>
    ),
  },
  fox: {
    name: 'Fox',
    emoji: '🦊',
    sounds: ['Clever fox, clever student!', '*pounces on the next topic*', 'Yip yip! Almost there!', 'Sly move, reviewing early.'],
    eyes: [{ cx: 47, cy: 50, r: 6.5 }, { cx: 73, cy: 50, r: 6.5 }],
    eyeWhite: '#F7C948',
    pupil: 'slit',
    tail: (
      <g className="pet-tail" style={{ transformOrigin: '84px 102px' }}>
        <path d="M82 104 C 112 104, 116 70, 99 64 C 105 80, 97 93, 82 95 Z" fill="#E8743B" />
        <path d="M99 64 C 106 70, 108 77, 106 84 C 101 78, 99 71, 99 64 Z" fill="#FFFFFF" />
      </g>
    ),
    body: (
      <>
        <ellipse cx="60" cy="98" rx="29" ry="20" fill="#E8743B" />
        <ellipse cx="60" cy="103" rx="15" ry="13" fill="#FFFFFF" />
        <ellipse cx="48" cy="114" rx="8" ry="5" fill="#3B2A22" />
        <ellipse cx="72" cy="114" rx="8" ry="5" fill="#3B2A22" />
      </>
    ),
    head: (
      <>
        <polygon points="28,40 32,6 54,26" fill="#E8743B" />
        <polygon points="34,33 35,15 47,26" fill="#3B2A22" />
        <polygon points="92,40 88,6 66,26" fill="#E8743B" />
        <polygon points="86,33 85,15 73,26" fill="#3B2A22" />
        <ellipse cx="60" cy="54" rx="33" ry="28" fill="#E8743B" />
        <path d="M27 56 Q40 80 60 75 Q80 80 93 56 Q80 66 60 63 Q40 66 27 56 Z" fill="#FFFFFF" />
        <ellipse cx="60" cy="64" rx="4.5" ry="3" fill={DARK} />
        <path d="M60 67 v2 M60 69 q-4 3 -7 0 M60 69 q4 3 7 0" stroke={DARK} strokeWidth="1.4" fill="none" strokeLinecap="round" />
      </>
    ),
  },
  hamster: {
    name: 'Hamster',
    emoji: '🐹',
    sounds: ['*stuffs cheeks with knowledge*', 'Squeak! Spin that wheel!', 'Snack break after this card?', '*tiny cheer* You can do it!'],
    eyes: [{ cx: 47, cy: 52, r: 5.5 }, { cx: 73, cy: 52, r: 5.5 }],
    eyeWhite: '#FFFFFF',
    iris: '#2A1E16',
    pupil: 'round',
    tail: null,
    body: (
      <>
        <ellipse cx="60" cy="98" rx="30" ry="20" fill="#F0B66E" />
        <ellipse cx="60" cy="102" rx="18" ry="14" fill="#FFF4E2" />
        <ellipse cx="60" cy="97" rx="3.5" ry="6" fill="#4A3A2A" />
        <path d="M60 92 v10" stroke="#EDE3D3" strokeWidth="1" />
        <circle cx="54" cy="98" r="3.5" fill="#F6B7B7" />
        <circle cx="66" cy="98" r="3.5" fill="#F6B7B7" />
        <ellipse cx="48" cy="115" rx="7" ry="4" fill="#F6B7B7" />
        <ellipse cx="72" cy="115" rx="7" ry="4" fill="#F6B7B7" />
      </>
    ),
    head: (
      <>
        <circle cx="34" cy="31" r="8" fill="#F0B66E" />
        <circle cx="34" cy="31" r="4.5" fill="#F6B7B7" />
        <circle cx="86" cy="31" r="8" fill="#F0B66E" />
        <circle cx="86" cy="31" r="4.5" fill="#F6B7B7" />
        <ellipse cx="60" cy="56" rx="35" ry="30" fill="#F0B66E" />
        <ellipse cx="60" cy="67" rx="23" ry="16" fill="#FFF4E2" />
        <circle cx="37" cy="64" r="9" fill="#FFF4E2" />
        <circle cx="83" cy="64" r="9" fill="#FFF4E2" />
        <circle cx="37" cy="64" r="4" fill="#F4A6A6" opacity="0.55" />
        <circle cx="83" cy="64" r="4" fill="#F4A6A6" opacity="0.55" />
        <path d="M57 61 h6 l-3 3 z" fill="#E88A9B" />
        <path d="M60 64 v2 M60 66 q-3 3 -6 1 M60 66 q3 3 6 1" stroke="#6B4A33" strokeWidth="1.3" fill="none" strokeLinecap="round" />
        <path d="M48 64 l-12 -3 M48 67 l-12 1 M72 64 l12 -3 M72 67 l12 1" stroke="#6B4A33" strokeWidth="0.9" opacity="0.55" strokeLinecap="round" />
      </>
    ),
  },
  owl: {
    name: 'Kabi the owl',
    emoji: '🦉',
    sounds: ['Hoo! Study today, pass tomorrow!', 'Hoo-hoo! Wise choice to review.', '*sleepy hoot* keep going', 'Hoo! That topic again?'],
    eyes: [{ cx: 46, cy: 52, r: 9 }, { cx: 74, cy: 52, r: 9 }],
    eyeWhite: '#FEF08A',
    iris: '#1E1E1E',
    pupil: 'round',
    tail: null,
    body: (
      <>
        <ellipse cx="60" cy="98" rx="29" ry="20" fill="#92400E" />
        <ellipse cx="60" cy="102" rx="17" ry="14" fill="#FED7AA" />
        <path d="M52 98 q8 5 16 0 M50 106 q10 5 20 0" stroke="#D97706" strokeWidth="1.8" fill="none" strokeLinecap="round" />
        <ellipse cx="50" cy="116" rx="6" ry="3" fill="#F59E0B" />
        <ellipse cx="70" cy="116" rx="6" ry="3" fill="#F59E0B" />
      </>
    ),
    head: (
      <>
        <polygon points="27,36 33,14 45,28" fill="#78350F" />
        <polygon points="93,36 87,14 75,28" fill="#78350F" />
        <ellipse cx="60" cy="54" rx="35" ry="31" fill="#92400E" />
        <circle cx="46" cy="52" r="13" fill="#FED7AA" />
        <circle cx="74" cy="52" r="13" fill="#FED7AA" />
        <path d="M56 61 L64 61 L60 69 Z" fill="#F59E0B" />
        <path d="M37 29 Q60 16 83 29 Q66 6 52 6 Z" fill="#D6C0B3" stroke="#493628" strokeWidth="1.5" />
        <circle cx="51" cy="6" r="4.5" fill="#FBBF24" />
      </>
    ),
  },
};

export const ANIMAL_KEYS = Object.keys(ANIMALS);

/* ==================== Chosen-animal preference (shared app-wide) ==================== */

const STORAGE_KEY = 'kabisado:companion';
const prefListeners = new Set();
let prefsCache = null;

function loadPrefs() {
  try {
    const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null');
    if (saved && ANIMALS[saved.animal]) return saved;
  } catch {
    // Storage unavailable: fall through to defaults
  }
  // Small screens start with the corner pet tucked away so it never covers quiz buttons or the chat box
  return { animal: 'cat', hidden: window.matchMedia?.('(max-width: 639px)').matches ?? false };
}

const readPrefs = () => (prefsCache ??= loadPrefs());

export function setPetPrefs(next) {
  prefsCache = { ...readPrefs(), ...next };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefsCache));
  } catch {
    // Preference just won't persist
  }
  prefListeners.forEach((listener) => listener());
}

/** { animal, hidden } — re-renders every subscriber when the student picks another buddy. */
export function usePetPrefs() {
  return useSyncExternalStore((listener) => {
    prefListeners.add(listener);
    return () => prefListeners.delete(listener);
  }, readPrefs);
}

/** The chosen buddy's emoji, for text like the footer and the browser tab icon. */
export function usePetEmoji() {
  return ANIMALS[usePetPrefs().animal].emoji;
}

/* ==================== Shared pointer position (one listener for every pet) ==================== */

let lastPointer = null;
const pointerListeners = new Set();
const onPointer = (e) => {
  lastPointer = { x: e.clientX, y: e.clientY };
  pointerListeners.forEach((listener) => listener(lastPointer));
};

export function subscribePointer(listener) {
  if (pointerListeners.size === 0) {
    window.addEventListener('pointermove', onPointer, { passive: true });
    window.addEventListener('pointerdown', onPointer, { passive: true });
  }
  pointerListeners.add(listener);
  return () => {
    pointerListeners.delete(listener);
    if (pointerListeners.size === 0) {
      window.removeEventListener('pointermove', onPointer);
      window.removeEventListener('pointerdown', onPointer);
    }
  };
}

/* ==================== Drawing ==================== */

function Eye({ eye, animal, mood, pupilRef }) {
  const { cx, cy, r } = eye;
  if (mood === 'blink' || mood === 'sleep') {
    return <path d={`M ${cx - r} ${cy} Q ${cx} ${cy + r * 0.75} ${cx + r} ${cy}`} stroke={DARK} strokeWidth="2.2" fill="none" strokeLinecap="round" />;
  }
  if (mood === 'happy') {
    return <path d={`M ${cx - r} ${cy + 2} Q ${cx} ${cy - r} ${cx + r} ${cy + 2}`} stroke={DARK} strokeWidth="2.4" fill="none" strokeLinecap="round" />;
  }
  // Shocked: bigger eyes, tiny pupils
  const shocked = mood === 'shocked';
  const er = shocked ? r * 1.2 : r;
  const pupilR = (animal.pupil === 'slit' ? er * 0.3 : er * 0.62) * (shocked ? 0.6 : 1);
  return (
    <g>
      <circle cx={cx} cy={cy} r={er} fill={shocked ? '#FFFFFF' : animal.eyeWhite} stroke={DARK} strokeWidth="1.2" />
      <g ref={pupilRef}>
        {animal.pupil === 'slit' && !shocked ? (
          <ellipse cx={cx} cy={cy} rx={er * 0.28} ry={er * 0.78} fill={DARK} />
        ) : (
          <>
            <circle cx={cx} cy={cy} r={pupilR} fill={animal.iris || DARK} />
            <circle cx={cx} cy={cy} r={pupilR * 0.5} fill={DARK} />
          </>
        )}
        <circle cx={cx + pupilR * 0.45} cy={cy - er * 0.35} r={Math.max(1.2, er * 0.18)} fill="#FFFFFF" />
      </g>
    </g>
  );
}

function Glasses({ eyes }) {
  const [a, b] = eyes;
  const r = a.r + 3.5;
  return (
    <g fill="none" stroke="#493628" strokeWidth="2.2">
      <circle cx={a.cx} cy={a.cy} r={r} />
      <circle cx={b.cx} cy={b.cy} r={r} />
      <path d={`M ${a.cx + r} ${a.cy} Q 60 ${a.cy - 4} ${b.cx - r} ${b.cy}`} />
    </g>
  );
}

/**
 * One animal, drawn in a given mood.
 * mood: 'open' | 'happy' | 'sleep' | 'shocked'. `glasses` adds reading glasses (the "studying" look).
 * `track` makes the eyes and head follow the cursor; awake pets also blink on their own.
 */
export function PetFigure({ animal: animalKey, mood = 'open', glasses = false, track = false, className = '', svgRef: outerRef }) {
  const animal = ANIMALS[animalKey] || ANIMALS.cat;
  const [blinking, setBlinking] = useState(false);
  const svgRef = useRef(null);
  const headRef = useRef(null);
  const pupilRefs = useRef([]);
  const frame = useRef(0);

  const awake = mood === 'open' || mood === 'shocked';
  const shownMood = mood === 'open' && blinking ? 'blink' : mood;

  const look = useCallback(() => {
    frame.current = 0;
    const svg = svgRef.current;
    if (!svg || !lastPointer) return;
    const rect = svg.getBoundingClientRect();
    if (!rect.width) return;
    const scale = rect.width / 120;
    const { x, y } = lastPointer;

    animal.eyes.forEach((eye, i) => {
      const el = pupilRefs.current[i];
      if (!el) return;
      const dx = x - (rect.left + eye.cx * scale);
      const dy = y - (rect.top + eye.cy * scale);
      const dist = Math.hypot(dx, dy) || 1;
      const reach = eye.r * (animal.pupil === 'slit' ? 0.55 : 0.38) * Math.min(1, dist / 160);
      el.setAttribute('transform', `translate(${((dx / dist) * reach).toFixed(2)} ${((dy / dist) * reach).toFixed(2)})`);
    });

    const hx = x - (rect.left + 60 * scale);
    const hy = y - (rect.top + 54 * scale);
    const tilt = Math.max(-10, Math.min(10, hx / 45));
    const shiftX = Math.max(-3, Math.min(3, hx / 120));
    const shiftY = Math.max(-2.5, Math.min(2.5, hy / 160));
    headRef.current?.setAttribute('transform', `rotate(${tilt.toFixed(2)} 60 84) translate(${shiftX.toFixed(2)} ${shiftY.toFixed(2)})`);
  }, [animal]);

  // Follow the pointer while awake
  useEffect(() => {
    if (!track || !awake) return undefined;
    const unsubscribe = subscribePointer(() => {
      if (!frame.current) frame.current = requestAnimationFrame(look);
    });
    return () => {
      unsubscribe();
      cancelAnimationFrame(frame.current);
      frame.current = 0;
    };
  }, [track, awake, look]);

  // Re-aim after the eyes re-render (after a blink, a mood change, or a new animal)
  useEffect(() => {
    if (track && awake && !blinking) look();
    if (!track || !awake) headRef.current?.removeAttribute('transform');
  }, [track, awake, blinking, shownMood, animalKey, look]);

  // Random blinking while awake
  useEffect(() => {
    if (mood !== 'open' || blinking) return undefined;
    const timer = setTimeout(() => setBlinking(true), 2500 + Math.random() * 3500);
    return () => clearTimeout(timer);
  }, [mood, blinking]);
  useEffect(() => {
    if (!blinking) return undefined;
    const timer = setTimeout(() => setBlinking(false), 140);
    return () => clearTimeout(timer);
  }, [blinking]);

  return (
    <svg
      ref={(el) => {
        svgRef.current = el;
        if (outerRef) outerRef.current = el;
      }}
      viewBox="0 0 120 120"
      className={`overflow-visible ${className}`}
      aria-hidden="true"
    >
      {animal.tail}
      <g className="pet-breathe" style={{ transformOrigin: '60px 118px' }}>{animal.body}</g>
      <g ref={headRef} style={{ transition: 'transform 120ms ease-out' }}>
        {animal.head}
        {animal.eyes.map((eye, i) => (
          <Eye
            key={`${animalKey}-${i}`}
            eye={eye}
            animal={animal}
            mood={shownMood}
            pupilRef={(el) => {
              pupilRefs.current[i] = el;
            }}
          />
        ))}
        {glasses && <Glasses eyes={animal.eyes} />}
      </g>
      {mood === 'sleep' && (
        <g className="animate-pulse" fill="#AB886D" fontWeight="bold">
          <text x="92" y="22" fontSize="14">Z</text>
          <text x="104" y="10" fontSize="10">z</text>
        </g>
      )}
    </svg>
  );
}
