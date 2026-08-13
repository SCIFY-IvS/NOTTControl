#pragma once
/* C++ STL include files */
#include <string>
#include <tuple>
#include <exception>
#include "TcBase.h"
#include "TcError.h"


std::uint16_t htobe16(const std::uint16_t value) {
	uint16_t tmp = value;
	return (tmp >> 8) | (tmp << 8);
}

std::uint16_t be16toh(const std::uint16_t value) {
	uint16_t tmp = value;
	return (tmp >> 8) | (tmp << 8);
}

std::uint32_t htobe32(const std::uint32_t value) {
	std::uint32_t tmp = value;
	std::uint32_t tmp2 = ((tmp << 8) & 0xFF00FF00) | ((tmp >> 8) & 0xFF00FF);
	return (tmp2 << 16) | (tmp2 >> 16);
}

std::uint32_t be32toh(const std::uint32_t value) {
	std::uint32_t tmp = value;
	std::uint32_t tmp2 = ((tmp << 8) & 0xFF00FF00) | ((tmp >> 8) & 0xFF00FF);
	return (tmp2 << 16) | (tmp2 >> 16);
}


std::uint64_t htobe64(const std::uint64_t value) {
	std::uint64_t tmp = value;
	tmp = ((tmp & 0x00000000FFFFFFFFull) << 32) | ((tmp & 0xFFFFFFFF00000000ull) >> 32);
	tmp = ((tmp & 0x0000FFFF0000FFFFull) << 16) | ((tmp & 0xFFFF0000FFFF0000ull) >> 16);
	tmp = ((tmp & 0x00FF00FF00FF00FFull) << 8) | ((tmp & 0xFF00FF00FF00FF00ull) >> 8);
	return tmp;
}

std::uint64_t be64toh(const std::uint64_t value) {
	std::uint64_t tmp = value;
	tmp = ((tmp & 0x00000000FFFFFFFFull) << 32) | ((tmp & 0xFFFFFFFF00000000ull) >> 32);
	tmp = ((tmp & 0x0000FFFF0000FFFFull) << 16) | ((tmp & 0xFFFF0000FFFF0000ull) >> 16);
	tmp = ((tmp & 0x00FF00FF00FF00FFull) << 8) | ((tmp & 0xFF00FF00FF00FF00ull) >> 8);
	return tmp;
}

namespace mudpiif {

	/**
	 * TYPEDEF for a MUDPI header. The structure is as follows:
	 *
	 * UINT32 TopicId         // Unique identifier of data topic
	 * UINT16 ComponentId     // Unique identifier of the sender
	 * UINT16 ApplicationTag  // For application use (not used by MUDPI)
	 * UINT16 Reserved1       // Reserved for future use
	 * UINT16 Version         // MUDPI version identifier
	 * UINT32 SampleId        // Rolling sample identifier (thus not unique, rather an incrementing number), incremented for each new sample
	 * UINT64 Timestamp       // Seconds since UNIX Epoch, following TAI time line
	 * UINT16 FrameId         // Frame counter for multi‐frame transmissions (starting from 1)
	 * UINT16 NumFrames       // Number of frames in a multi‐part message
	 * UINT16 PayloadSize     // Size in bytes of the payload
	 * UINT16 Reserved2       // Reserved for future use
	 */
#define PACK( __Declaration__ ) __pragma( pack(push, 1) ) __Declaration__ __pragma( pack(pop))

	PACK(struct mudpiHeaderType {
		uint32_t topicId;
		uint16_t componentId;
		uint16_t applicationTag;
		uint16_t reserved1;
		uint16_t version;
		uint32_t sampleId;
		uint64_t timestamp;
		uint16_t frameId;
		uint16_t numFrames;
		uint16_t payloadSize;
		uint16_t reserved2;
	});

	/**
	 * MUDPI constants
	 */
	const size_t MUDPI_PACKET_SIZE = 1500; /* = IEEE802.3 ethernet basic frame payload */
	const size_t MUDPI_PACKET_SIZE_JUMBO = 9000;
	const uint16_t MUDPI_VERSION = 1;
	const size_t IPV4_HEADER_SIZE = 20;
	const size_t UDP_HEADER_SIZE = 8;
	const size_t MUDPI_PAYLOAD_SIZE = MUDPI_PACKET_SIZE - IPV4_HEADER_SIZE - UDP_HEADER_SIZE - sizeof(mudpiHeaderType);
	const size_t MUDPI_PAYLOAD_SIZE_JUMBO = MUDPI_PACKET_SIZE_JUMBO - IPV4_HEADER_SIZE - UDP_HEADER_SIZE - sizeof(mudpiHeaderType); // includes CRC



	/**
	 * (Template) class definition for a MUDPI packet.

	 * NOTE: All attributes are internally encoded in big-endian format
	 */
	template <size_t maxSize>
	class mudpiPacketBase {
	public:
		mudpiPacketBase(uint32_t topicId, uint16_t componentId);
		mudpiPacketBase(const char *inputData, size_t size);
		mudpiPacketBase();
		~mudpiPacketBase() {}

		// Copy constructor
		mudpiPacketBase(const mudpiPacketBase &p2);

		bool verifyPacket();
		bool verifyCRC();

		unsigned long size();
		const char* data();

		void increaseSampleId();

		
		void setTopicId(const uint32_t topicId) { mData.header.topicId = htobe32(topicId); }
		void setComponentId(const uint16_t componentId) { mData.header.componentId = htobe16(componentId); }
		void setApplicationTag(const uint16_t applicationTag) { mData.header.applicationTag = htobe16(applicationTag); }
		void setVersion(const uint16_t version) { mData.header.version = htobe16(version); }
		void setSampleId(const uint32_t sampleId) { mData.header.sampleId = htobe32(sampleId); }
		void setTimestamp(const double timestamp);
		void setFrameId(const uint16_t frameId) { mData.header.frameId = htobe16(frameId); }
		void setNumFrames(const uint16_t numFrames) { mData.header.numFrames = htobe16(numFrames); }
		void setPayloadSize(const uint16_t payloadSize) { mData.header.payloadSize = htobe16(payloadSize); }
		void setCRC(const uint16_t crc);
		void setPayload(const std::string payload);
		void setPayload(const char *payload, uint16_t payloadSize);

		
		uint32_t getTopicId() { return be32toh(mData.header.topicId); }
		uint16_t getComponentId() { return be16toh(mData.header.componentId); }
		uint16_t getApplicationTag() { return be16toh(mData.header.applicationTag); }
		uint16_t getVersion() { return be16toh(mData.header.version); }
		uint32_t getSampleId() { return be32toh(mData.header.sampleId); }
		double   getTimestamp(); 
		uint16_t getFrameId() { return be16toh(mData.header.frameId); }
		uint16_t getNumFrames() { return be16toh(mData.header.numFrames); }
		uint16_t getPayloadSize() { return be16toh(mData.header.payloadSize); }
		uint16_t getCRC();
		const char* getPayload() { return &(mData.data[0]); }
		uint16_t calculateCRC();
		size_t getMaxPayloadSize();

	private:
		struct mudpiDataType {
			struct mudpiHeaderType header;
			char                   data[maxSize];
		};

		struct mudpiDataType mData;
	};

	/**
	 * Constructor variant #1 for a MUDPI packet: Specifies topicId and componentId.
	 */
	template <size_t maxSize>
	mudpiPacketBase<maxSize>::mudpiPacketBase(uint32_t topicId, uint16_t componentId) {
		memset(reinterpret_cast<char*>(&mData), 0, sizeof(struct mudpiHeaderType));
		setVersion(MUDPI_VERSION);
		setFrameId(1);
		setNumFrames(1);
		setTopicId(topicId);
		setComponentId(componentId);
		uint16_t crc = calculateCRC();
		setCRC(crc);
	}

	/**
	 * Constructor variant #2 for a MUDPI packet: Create the data structure from a stream of bytes.
	 */
	template <size_t maxSize>
	mudpiPacketBase<maxSize>::mudpiPacketBase(const char *inputData, size_t size) {
		size_t tmp = maxSize + sizeof(mudpiHeaderType);
		if (size <= tmp) {
			memcpy(reinterpret_cast<char*>(&mData), inputData, size);
		}
		/*
		else {
			throw std::overflow_error("Input data too large for MUDPI packet");
		}
		*/
	}

	/**
	 * Constructor variant #3 for a MUDPI packet: Use only zero values for a empty packet.
	 */
	template <size_t maxSize>
	mudpiPacketBase<maxSize>::mudpiPacketBase() {
		memset(reinterpret_cast<char*>(&mData), 0, sizeof(struct mudpiHeaderType));
		setCRC(0);
	}

	/**
	 * Copy constructor
	 */
	template <size_t maxSize>
	mudpiPacketBase<maxSize>::mudpiPacketBase(const mudpiPacketBase &p2) {
		memcpy(&mData.header, &p2.mData.header, sizeof(struct mudpiHeaderType));
		uint16_t payloadSize = be16toh(p2.mData.header.payloadSize) + sizeof(uint16_t);
		memcpy(mData.data, p2.mData.data, payloadSize);
	}

	/**
	 * This function verifies, if the internal structure of a MUDPI packet is correct.
	 */
	template <size_t maxSize>
	bool mudpiPacketBase<maxSize>::verifyPacket() {
		uint16_t version = getVersion();
		uint16_t frameId = getFrameId();
		uint16_t numFrames = getNumFrames();
		uint32_t topicId = getTopicId();
		uint16_t componentId = getComponentId();
		bool crcCorrect = verifyCRC();
		bool packetCorrect = (version == MUDPI_VERSION) && (frameId <= numFrames) && (topicId != 0) && (componentId != 0);
		return (packetCorrect && crcCorrect);
	}

	/**
	 * This function verifies, if the CRC of a MUDPI packet is correct.
	 *
	 * @return TRUE = CRC does match the content of the packet, FALSE = CRC does not match.
	 */
	template <size_t maxSize>
	bool mudpiPacketBase<maxSize>::verifyCRC() {
		uint16_t crc1 = getCRC();
		uint16_t crc2 = calculateCRC();
		// The MUDPI standard allows to omit the checksum calculation
		if ((crc1 == 0) || (crc2 == 0)) {
			return true;
		}
		else {
			return (crc1 == crc2);
		}
	}

	/**
	 * This function returns the size of the MUDPI packet in bytes.
	 *
	 * @return Size of the packet in bytes, i.e. MUDPI header + payload + CRC.
	 */
	template <size_t maxSize>
	unsigned long mudpiPacketBase<maxSize>::size() {
		uint16_t payloadSize = getPayloadSize();
		unsigned long size = sizeof(struct mudpiHeaderType);
		size += static_cast<size_t>(payloadSize) + sizeof(uint16_t); // + CRC
		return size;
	}

	/**
	 * @return A pointer to the packet, be aware that the contents are big-endian!
	 */
	template <size_t maxSize>
	const char* mudpiPacketBase<maxSize>::data() {
		return reinterpret_cast<const char*>(&mData);
	}

	/**
	 * This function increases the sample ID of the MUDPI packet.
	 */
	template <size_t maxSize>
	void mudpiPacketBase<maxSize>::increaseSampleId() {
		// ETCS-247: Fixed size mismatch
		uint32_t mySampleId = getSampleId();
		setSampleId(++mySampleId);
		uint16_t crc = calculateCRC();
		setCRC(crc);
	}

	/**
	 * This function sets the timestamp of a MUDPI packet.
	 *
	 * @param timestamp Seconds since UNIX Epoch, following TAI time line.
	 */
	template <size_t maxSize>
	void mudpiPacketBase<maxSize>::setTimestamp(const double timestamp) {
		uint64_t timestampLocal;
		memcpy(reinterpret_cast<char*>(&timestampLocal), reinterpret_cast<const char*>(&timestamp), sizeof(uint64_t));
		mData.header.timestamp = htobe64(timestampLocal);
		uint16_t crc = calculateCRC();
		setCRC(crc);
	}

	/**
	 * This function returns the timestamp of a MUDPI packet.
	 *
	 * @return timestamp Seconds since UNIX Epoch, following TAI time line.
	 */
	template <size_t maxSize>
	double mudpiPacketBase<maxSize>::getTimestamp() {
		double timestampLocal;
		uint64_t tmp = be64toh(mData.header.timestamp);
		memcpy(reinterpret_cast<char*>(&timestampLocal), reinterpret_cast<const char*>(&tmp), sizeof(uint64_t));
		return timestampLocal;
	}

	/**
	 * This function sets the CRC of a MUDPI packet.
	 *
	 * @param CRC crc-16 value to be set in the packet.
	 */
	template <size_t maxSize>
	void mudpiPacketBase<maxSize>::setCRC(uint16_t crc) {
		uint16_t payloadSize = getPayloadSize();
		memcpy(&(mData.data[payloadSize]), reinterpret_cast<const char*>(&crc), sizeof(uint16_t));
	}

	/**
	 * This function sets the payload of a MUDPI packet. The packet CRC is calculated again.
	 *
	 * @param payload: the content of the string, and the size are copied to the MUDPI packet.
	 */
	template <size_t maxSize>
	void mudpiPacketBase<maxSize>::setPayload(const std::string payload) {
		uint16_t payloadSize = payload.size();
		if (payloadSize > (maxSize - sizeof(uint16_t))) {
			throw std::overflow_error("Payload too large for MUDPI packet");
		}
		else {
			if (payloadSize > 0) {
				setPayloadSize(payloadSize);
				memcpy(reinterpret_cast<char*>(&mData.data[0]), payload.data(), payloadSize);
				uint16_t crc = calculateCRC();
				setCRC(crc);
			}
		}
	}

	/**
	 * This function sets the payload of a MUDPI packet. The packet CRC is calculated again.
	 *
	 * @param payload: C-pointer to any data.
	 * @param payloadSize: Size of payload data in bytes.
	 */
	template <size_t maxSize>
	void mudpiPacketBase<maxSize>::setPayload(const char *payload, uint16_t payloadSize) {
		if (payloadSize <= (maxSize - sizeof(uint16_t))) {
			if (payloadSize > 0) {
				setPayloadSize(payloadSize);
				memcpy(reinterpret_cast<char*>(&mData.data[0]), payload, payloadSize);
				uint16_t crc = calculateCRC();
				setCRC(crc);
			}
		}
	}

	/**
	 * This function returns the payload of a MUDPI packet.
	 *
	 * @return CRC16 value of the MUDPI packet.
	 */
	template <size_t maxSize>
	uint16_t mudpiPacketBase<maxSize>::getCRC() {
		uint16_t payloadSize = getPayloadSize();
		uint16_t crc;
		memcpy(reinterpret_cast<char*>(&crc), &(mData.data[payloadSize]), sizeof(uint16_t));
		return crc;
	}

	/**
	 * This function calculates the CRC16 of the MUDPI packet (header and payload, of present).
	 *
	 * @return CRC16 value of the payload.
	 */
	template <size_t maxSize>
	uint16_t mudpiPacketBase<maxSize>::calculateCRC() {
		uint16_t packetSize = getPayloadSize();
		packetSize += sizeof(struct mudpiHeaderType);
		const uint16_t *data = reinterpret_cast<uint16_t*>(&(mData.header));
		uint32_t sum = 0;
		// Calculate 1's complement sum of the data
		while (packetSize > 1) {
			sum += *data++;
			if (sum & 0x80000000) {
				sum = (sum & 0xFFFF) + (sum >> 16);
			}
			packetSize -= sizeof(uint16_t);
		}
		if (packetSize & 1) {
			sum += *((uint8_t*)data);
		}
		// Add carry-over
		while (sum >> 16) {
			sum = (sum & 0xFFFF) + (sum >> 16);
		}
		return static_cast<uint16_t>(~sum);
	}

	/**
	 * @return Return maximum payload size.
	 */
	template <size_t maxSize>
	size_t mudpiPacketBase<maxSize>::getMaxPayloadSize() {
		return maxSize;
	}

	/**
	 * Typedef-shortcuts for normal and jumbo-sized mudpiPackets.
	 */

	typedef mudpiPacketBase<MUDPI_PAYLOAD_SIZE>       mudpiPacket;
	typedef mudpiPacketBase<MUDPI_PAYLOAD_SIZE_JUMBO> mudpiPacketJumbo;

}  // namespace mudpiif