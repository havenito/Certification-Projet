"use client";

import { motion } from "framer-motion";
import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";

export default function HomeCard({ icon, title, description, href, button, delay = 0, isPremium = false }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay }}
      className={`rounded-2xl p-8 shadow-xl flex flex-col items-center hover:scale-[1.025] transition ${
        isPremium 
          ? "bg-gradient-to-br from-[#1a1a1a] via-[#23272f] to-[#1a1a1a] border-2 border-yellow-500/60 shadow-yellow-500/20" 
          : "bg-[#1b1b1b] border border-[#23272f]"
      }`}
    >
      {isPremium && (
        <div className="absolute top-3 right-3 text-yellow-500">
          <motion.div
            animate={{ rotate: [0, 10, -10, 0] }}
            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
          >
            <FontAwesomeIcon icon={icon} className="text-xl" />
          </motion.div>
        </div>
      )}
      <div className={`flex items-center justify-center w-16 h-16 rounded-full shadow mb-4 ${
        isPremium 
          ? "bg-gradient-to-br from-yellow-400 to-yellow-600" 
          : "bg-[#90EE90]"
      }`}>
        <FontAwesomeIcon icon={icon} className={`text-3xl ${
          isPremium ? "text-black" : "text-black"
        }`} />
      </div>
      <h2 className={`text-2xl font-bold mb-2 text-center ${
        isPremium ? "text-yellow-400" : "text-[#90EE90]"
      }`}>{title}</h2>
      <p className={`mb-6 text-center text-sm ${
        isPremium ? "text-gray-200" : "text-gray-300"
      }`}>{description}</p>
      <a
        href={href}
        className={`px-6 py-3 font-semibold rounded-xl shadow hover:scale-105 transition ${
          isPremium 
            ? "bg-gradient-to-r from-yellow-400 to-yellow-500 text-black hover:from-yellow-300 hover:to-yellow-400" 
            : "bg-[#90EE90] text-black"
        }`}
      >
        {button}
      </a>
    </motion.div>
  );
}