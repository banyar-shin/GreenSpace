import React from "react";
import Image from "next/image";

export default function Navbar() {
  return (
    <>
      <nav className="flex px-60 w-full justify-between items-center">
        <a href="/">
          <Image
            src="/GreenSpace.png"
            width={128}
            height={128}
            alt="Greenspace logo"
            className="cursor-pointer tranform hover:scale-90 duration-300 ease-in-out"
          />
        </a>
        <a
          href="/generate"
          className="px-10 py-3 font-bold text-white bg-sky-600 text-xl transition-all shadow-[3px_3px_0px_black] hover:shadow-none hover:translate-x-[3px] hover:translate-y-[3px]"
        >
          Get Started
        </a>
      </nav>
    </>
  );
}
